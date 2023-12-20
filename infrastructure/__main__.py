import pulumi
import pulumi_aws as aws
from dotenv import load_dotenv
import json
import os

load_dotenv(override=True)

cluster_name = "prefect-ecs-cluster"
project_name = "dataflow"
aws_accout_id = aws.get_caller_identity().account_id
aws_region = aws.get_region()

# note: for the infrastructure creation pulumi will assume an AWS IAM role,
# which  you have to create in advance (see readme of the repo).
# You will need to provide the arn of the role to the pulumi program as
# 'AWS_IAM_ROLE_TO_ASSUME' environment variable by:
# a) adding it to the .env file in your infrastructure folder, if you want to
# run the 'pulumi up' command locally on your computer
# b) adding it in your Github Action to the environment variables section of the step
# (this is alread prepared for this project) and add the
# arn of the role to your GitHub repos' Secrets (secret name: AWS_IAM_ROLE_TO_ASSUME)

# Setup the AWS provider to assume a specific role
assumed_role_provider = aws.Provider(
    "assumedRoleProvider",
    assume_role=aws.ProviderAssumeRoleArgs(
        role_arn=os.getenv("AWS_IAM_ROLE_TO_ASSUME"),
        session_name="PulumiSession_ecr_ecs",
    ),
    region=aws_region.name,
)

# Create an ECR Repository
ecr_repo = aws.ecr.Repository(
    project_name + "_ecr",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


# Create an ECS Cluster
ecs_cluster = aws.ecs.Cluster(
    cluster_name,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# Create VPC and necessary igw, subnet, route table for push work pool

vpc = aws.ec2.Vpc(
    "dataflow_vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

igw = aws.ec2.InternetGateway(
    "dataflow_internet_gateway",
    vpc_id=vpc.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


route_table = aws.ec2.RouteTable(
    "dataflow_route_table",
    vpc_id=vpc.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

route = aws.ec2.Route(
    "dataflow_route",
    route_table_id=route_table.id,
    destination_cidr_block="0.0.0.0/0",
    gateway_id=igw.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

ecs_service_subnet = aws.ec2.Subnet(
    "dataflow_subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.0.0/16",
    map_public_ip_on_launch=True,
    availability_zone="eu-central-1a",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


# Associate the Route Table with the Subnet
route_table_association = aws.ec2.RouteTableAssociation(
    "dataflow_route_table_association",
    subnet_id=ecs_service_subnet.id,
    route_table_id=route_table.id,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


execution_role = aws.iam.Role(
    "dataflow_execution_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                }
            ],
        }
    ),
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

execution_role_policy = aws.iam.RolePolicy(
    "dataflow_execution_role_policy",
    role=execution_role.name,
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "logs:PutLogEvents",
                    ],
                    "Effect": "Allow",
                    "Resource": "arn:aws:logs:*:*:*",
                }
            ],
        }
    ),
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


aws.iam.RolePolicyAttachment(
    "ecsPolicyAttachment",
    role=execution_role.name,
    policy_arn="arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


task_role = aws.iam.Role(
    "dataflow_task_role",
    assume_role_policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
                }
            ],
        }
    ),
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


task_role_policy = aws.iam.RolePolicy(
    "dataflow_task_role_policy",
    role=task_role.name,
    policy=json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": [
                        "logs:CreateLogStream",
                        "ecs:RegisterTaskDefinition",
                        "ecs:DeregisterTaskDefinition",
                        "ecs:DescribeTasks",
                        "ecs:RunTask",
                        "logs:GetLogEvents",
                        "ec2:DescribeSubnets",
                        "ec2:DescribeVpcs",
                    ],
                    "Effect": "Allow",
                    "Resource": "*",
                },
            ],
        }
    ),
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)

# note: you need to provide also the AWS IAM username as environment variable
# (same procedure as for the IAM role) which is used for the execution of
# the prefect flow (for which you provided the aws credentials to prefect)

# Following policies will be attached to your IAM User to make the Prefet ecs:push work pool run:
# - "ecs:RegisterTaskDefinition",
# - "ecs:RunTask",
# - "ec2:DescribeVpcs",
# - "ec2:DescribeSubnets",
# - "iam:PassRole",
# the remaining policies are needed for the GitHub Actions to execute ecr authentication (private ecr repo):
# see also https://github.com/aws-actions/amazon-ecr-login/tree/v1/#ecr-public
# All Policies, which are added here to your IAM User will be deleted again when "pulumi destroy" is executed

iam_policy = aws.iam.Policy(
    "prefect_ecs_push_policies",
    policy=ecr_repo.arn.apply(
        lambda ecr_arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": [
                            "ecs:RegisterTaskDefinition",
                            "ec2:DescribeVpcs",
                            "ec2:DescribeSubnets",
                            "ecs:RunTask",
                            "iam:PassRole",
                            "ecr:GetAuthorizationToken",
                        ],
                        "Effect": "Allow",
                        "Resource": "*",
                    },
                    {
                        "Action": [
                            "ecr:BatchGetImage",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:CompleteLayerUpload",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:InitiateLayerUpload",
                            "ecr:PutImage",
                            "ecr:UploadLayerPart",
                            "ecr:ListImages",
                            "ecr:BatchDeleteImage",
                        ],
                        "Effect": "Allow",
                        "Resource": ecr_arn,
                    },
                ],
            }
        )
    ),
    description="Policies for Prefect ecs:push work pool and Github Action ecr authentication",
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


# Attach the policy to your IAM user
user_policy_attachment = aws.iam.UserPolicyAttachment(
    "prefect-policy-attachment",
    user=os.getenv("AWS_IAM_USER_NAME"),
    policy_arn=iam_policy.arn,
    opts=pulumi.ResourceOptions(provider=assumed_role_provider),
)


pulumi.export("vpc_id", vpc.id)
pulumi.export("ecs_cluster_arn", ecs_cluster.arn)
pulumi.export("iam_execution_role_arn", execution_role.arn)
pulumi.export("iam_task_role_arn", task_role.arn)
pulumi.export("ecr_repo_url", ecr_repo.repository_url)
pulumi.export("ecr_repo_name", ecr_repo.name)
