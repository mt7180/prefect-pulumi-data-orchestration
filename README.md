# prefect-pulumi-data-orchestration

event-driven serverless dataflows and infrastructure on demand with Prefect (flows + AWS ECS push workpool + webhook) and Pulumi

---

## Details
- aws infrastructure like ecr repo, ecs cluster, vpc, execution role and task role has to be created via pulumi up command in the infrastructure directory (to be put into gh action)
- by executing python -m etl.dataflow in the root directory, the dataflow will be deployed to prefect cloud and the flow image pushed to the aws ecr repo. The deployment job_variables define the infrastructure to use for this deployment (created by pulumi up) and have to be updated in the .env file 
- event-driven: After signing up for the entsoe web service, new energy forecast data is sent from entsoe transparency platform **as soon as it is available** to a previously created prefect webhook, which creates a prefect event from it
- this event triggers a prefect automation, which in turn  triggers the prefect flow deployment to run on the ecs cluster
- an aws task definition is created by the prefect push workpool (no service is running on the ecs cluster until the workpool initiates the task definition and runs it)
- the flow run is executed  => the event data will be extracted and processed/ transformed and finally an update newsletter sent via email to registered users.  



## Resources
- https://transparency.entsoe.eu/
- https://docs.prefect.io/latest/
- https://www.pulumi.com