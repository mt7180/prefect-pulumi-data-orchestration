# prefect-pulumi-data-orchestration

## Example project to create event-driven serverless dataflows and infrastructure on demand with Prefect + AWS ECS push workpool + webhook + automation, Pulumi and entsoe

---

## Prerequisits
1. Sign up for Prefect Cloud and create a workspace and push aws:ecs push workpool (todo: implement in gh action)
2. Sign up for AWS and assign the necessary permissions to your IAM user (todo: give list of policies for ECR, ECS ...) 
3. Sign up for the entsoe transparency platform and ask for Restful API access and Data Consumer subscription for private use (todo: put link)

## Details
1. Deploy necessary AWS infrastructure and prefect flow with one click on Github with Github Action: gh_action_init_dataflow.yaml. This will trigger the following:
    - AWS infrastructure like ECR repo, ECS cluster, VPC, execution role and task role are created via pulumi up command in the gh action
    - a Prefect webhook is created, which can receive the entsoe web service message. You have to save the webhook url (can be found on prefect cloud ui) to the entsoe subscription channel on the transparency platform.
    - Finally the gh action executes python -m etl.dataflow, which deploys the dataflow to prefect cloud and the flow image will be pushed to the AWS ECR repo. The deployment job_variables define the infrastructure to use for this deployment (created by pulumi up) and are fed into the deployment script via env variables. The deployment also creates the prefect automation by setting the triggers parameter.
    
- event-driven: After signing up for the entsoe web service and subscribing for the Solar and Wind Generation Forecast, new generation forecast data is sent from entsoe transparency platform **as soon as it is available** to the previously created prefect webhook, which creates a prefect event from it
- this event triggers the prefect automation (set with triggers in the deployment), which in turn triggers the prefect flow deployment to run on the ecs cluster
- an aws task definition is created by the prefect push workpool (no service is running on the ecs cluster until the workpool initiates the task definition and runs it)
- the flow run is executed  => the event data will be extracted, processed and finally a newsletter is sent via email to registered users.  



## Resources
- https://transparency.entsoe.eu/
- https://docs.prefect.io/latest/
- https://www.pulumi.com