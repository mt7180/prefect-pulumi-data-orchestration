
import pathlib
from prefect_email import EmailServerCredentials, email_send_message
from prefect import task, flow
from prefect.blocks.system import Secret, String
from entsoe.parsers import parse_generation as entsoe_generation_parser
from entsoe import EntsoePandasClient
import pandas as pd

from etl.utils import get_users, User
from etl.utils import mock_event_data


@task
def extract_event_payload(event_msg: str):
    return event_msg.split("<msg:Payload>")[1]


@task(retries=3, retry_delay_seconds=60)
def extract_installed_capacity():
    entsoe_api_key = Secret.load("entsoe-api-key").get()
    now = pd.Timestamp.today(tz="Europe/Brussels")
    e_client = EntsoePandasClient(entsoe_api_key)
    return e_client.query_installed_generation_capacity(
        "DE",
        start=pd.Timestamp(year=now.year, month=1, day=1, tz="Europe/Brussels"),
        end=now,
    )


@task(retries=3, retry_delay_seconds=60)
def transform_data(xml_str: str, installed_offshore_s: pd.DataFrame) -> pd.DataFrame:

    forecast_offshore_df = entsoe_generation_parser(xml_str)
    
    # filter data
    forecast_offshore_df = forecast_offshore_df.loc[forecast_offshore_df.index.minute == 0]
    column_name = forecast_offshore_df.columns[0]
    result_df = pd.DataFrame(
        data={'forecast': forecast_offshore_df[column_name], 'installed': installed_offshore_s.iloc[0]}, 
        index=forecast_offshore_df.index,
    )

    chart_data = []
    print("Intraday Generation Forecasts Wind Offshore")
    for index, row in result_df.iterrows():
        percentage = int(row["forecast"]/ row["installed"]*100)
        chart_data.append(
            f"{index} | {'#'*percentage}{'_'*(100-percentage)}"
            f"  => {percentage}% ({row['forecast']}MW/{row['installed']}MW)"
        )
    
    return {"chart":"<br>".join(chart_data), "df":result_df}
    


def send_newsletters(data: pd.DataFrame):
    """in this example the data won't be loaded into a database, 
    but will be sent to registered users
    """
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    users = get_users()

    for user in users:
        line1 = f"Hello {user.name}, <br>"
        line2 = f"Please find our lastest update on: <br><br>"
        line3 = "<h1>Intraday Generation Forecasts Wind Offshore:</h1>"
        # this is a prefect task:
        email_send_message.with_options(name="send-user-newsletter").submit(
            email_server_credentials=email_server_credentials,
            subject=f"Newsletter: Intraday Generation Forecasts Wind Offshore",
            msg=line1+line2+line3+data["chart"]+"<br><br>"+data["df"].to_html(),
            email_to=user.email,
        )

@flow
def data_flow(event_msg: str):
    event_payload = extract_event_payload(event_msg)
    installed_capacity_offshore = extract_installed_capacity().get("Wind Offshore", default=pd.Series())
    data = transform_data(event_payload, installed_capacity_offshore)
    send_newsletters(data)

if __name__ == "__main__":
    LOCAL = False
    ## 1. test with mocked event data and run locally without deployment
    if LOCAL:
        data_flow(mock_event_data())

    ## 2. test by running locally in a docker container, put event data manually via quick run in ui
    # from prefect.deployments.runner  import DeploymentImage
    # cfd = pathlib.Path(__file__).parent

    # data_flow.deploy(
    #     "deploy_dataflow_ecs_push", 
    #     # work_pool_name="Miras-push-workpool-2",
    #     work_pool_name="newsletter_docker_workpool",
    #     image=DeploymentImage(
    #         name="newsletter-flow_local",
    #         tag="test",
    #         dockerfile=cfd / "Dockerfile",
    #     ),
    #     build=True,
    #     push=False,
    # )
    
    else:
        # 3. if everything works, push image to ecr and deploy to push work pool
        import os
        from dotenv import load_dotenv
        from prefect.deployments.runner  import DeploymentImage
        cfd = pathlib.Path(__file__).parent

        load_dotenv(override=True)

        # 3.a: go into infrastructure folder and execute command: pulumi up
        # 3.b: put pulumi output to .env file

        # 3.c: You need to authenticate to aws ecr first:
        # aws ecr get-login-password --region region | docker login --username AWS --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com
        # replace: aws_account_id and region
        data_flow.deploy(
            "deploy_dataflow_ecs_push", 
            work_pool_name="Miras-push-workpool-2",
            job_variables={
                "execution_role_arn": os.getenv("EXECUTION_ROLE", ""),
                "task_role_arn": os.getenv("TASK_ROLE", ""),
                "cluster": os.getenv("ECS_CLUSTER"),
                "vpc_id": os.getenv("VPC_ID", ""),
                "container_name": "newsletter-flow_ecr-f66b601",
                "family": "newsletter-flow"
            },
            image=DeploymentImage(
                name=os.getenv("IMAGE_NAME", ""),
                tag=os.getenv("IMAGE_TAG"),
                dockerfile=cfd / "Dockerfile",
            ),
            build=True,
            push=True,
        )

