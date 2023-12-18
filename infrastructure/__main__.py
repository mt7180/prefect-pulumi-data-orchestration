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

# ecr_lifecycle_policy = aws.ecr.LifecyclePolicy(
#     "ecr_lifecycle_policy",
#     repository=ecr_repo.name,
#     policy=json.dumps(
#         {
#             "rules": [
#                 {
#                     "rulePriority": 1,
#                     "description": "Keep only one untagged image, expire all others",
#                     "selection": {
#                         "tagStatus": "untagged",
#                         "countType": "imageCountMoreThan",
#                         "countNumber": 1,
#                     },
#                     "action": {"type": "expire"},
#                 }
#             ]
#         }
#     ),
#  #   opts=pulumi.ResourceOptions(provider=assumed_role_provider),
# )


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
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameters",
                    ],
                    "Resource": "*",
                },
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


pulumi.export("vpc_id", vpc.id)
pulumi.export("ecs_cluster_arn", ecs_cluster.arn)
pulumi.export("iam_execution_role_arn", execution_role.arn)
pulumi.export("iam_task_role_arn", task_role.arn)
pulumi.export("ecr_repo_url", ecr_repo.repository_url)
pulumi.export("ecr_repo_name", ecr_repo.name)
