# prefect-pulumi-data-orchestration

## Orchestrating Event-driven Data Pipelines and Architecture with Prefect + Pulumi + AWS: 
### An Example Project using the new Prefect Features such as ECS:push Work Pool, Webhook & Automation to Detect and Process Incoming Data from entso-e Transparency Platform and Orchestrate the Dataflow Serverless with Python

---

### Prerequisits
1. Sign up for Prefect Cloud and create a workspace and aws:ecs push workpool (todo: implement in gh action)
2. Sign up for AWS and assign the necessary permissions to your IAM user (todo: give list of policies for ECR, ECS ...) 
3. Sign up for the entsoe transparency platform and ask for Restful API access and Data Consumer subscription for private use (todo: put link)
4. Add the following secrets to your github repo action secrets: AWS_ACCESS_KEY, AWS_SECRET_ACCESS_KEY, PULUMI_ACCESS_TOKEN, PREFECT_API_KEY, PREFECT_WORKSPACE (todo: explain where and how to get them)
5. Add the entsoe-api-key to a Secret-Block in Prefect UI (could be included in gh action)
6. Add Email-Credentials to Prefect Block
7. Add test-user email to Prefect String-Block or use own database
8. Add AWS Credentials Block to use ECS Push workpool

## Details
1. Deploy necessary AWS infrastructure and prefect flow with one click on Github with Github Action: gh_action_init_dataflow.yaml. This will trigger the following:
    - AWS infrastructure like ECR repo, ECS cluster, VPC, execution role and task role are created via pulumi up command in the gh action
    - a Prefect webhook is created, which can receive the entsoe web service message. You have to save the webhook url (can be found on prefect cloud ui) to the entsoe subscription channel on the transparency platform.
    - Finally the gh action executes python -m etl.dataflow, which deploys the dataflow to prefect cloud and the flow image will be pushed to the AWS ECR repo. The deployment job_variables define the infrastructure to use for this deployment (created by pulumi up) and are fed into the deployment script via env variables. The deployment also creates the prefect automation by setting the triggers parameter.
    
- event-driven: After signing up for the entsoe web service and subscribing for the Solar and Wind Generation Forecast, new generation forecast data is sent from entsoe transparency platform **as soon as it is available** to the previously created prefect webhook url, which creates a prefect event from it
- this event triggers the prefect automation (set with triggers in the deployment), which in turn triggers the prefect flow deployment to run on the ecs cluster
- therefore, an aws task definition is created automatically by the prefect push workpool (no service is running on the ecs cluster until the workpool initiates the task definition and runs it)
- the flow run is executed  => the event data will be extracted, processed and finally a newsletter is sent via email to registered users.  



## Resources
- https://transparency.entsoe.eu/
- https://docs.prefect.io/latest/
- https://www.pulumi.com
- https://annageller.medium.com/serverless-real-time-data-pipelines-on-aws-with-prefect-ecs-and-github-actions-1737c80da3f5#655e