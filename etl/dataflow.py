from enum import Enum
import pathlib
import requests
from typing import Any, Dict, List
from prefect_email import EmailServerCredentials, email_send_message
from prefect import task, flow
from prefect.blocks.system import Secret
from entsoe.parsers import parse_generation as entsoe_generation_parser
from entsoe import EntsoePandasClient
import pandas as pd

from etl.utils import User, get_users
from etl.utils import mock_event_data


@task
def extract_event_payload(event_msg: str) -> str:
    return event_msg.split("<msg:Payload>")[1]


@task(retries=3, retry_delay_seconds=30, log_prints=True)
def extract_installed_capacity() -> pd.DataFrame:
    # entsoe_api_key = "" # if you don't have one yet
    entsoe_api_key = Secret.load("entsoe-api-key").get()
    now = pd.Timestamp.today(tz="Europe/Brussels")
    e_client = EntsoePandasClient(entsoe_api_key)
    try:
        return e_client.query_installed_generation_capacity(
            "DE",
            start=pd.Timestamp(year=now.year, month=1, day=1, tz="Europe/Brussels"),
            end=now,
        )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Authentication failed")
            return pd.DataFrame()
        else:
            raise


@task(retries=3, retry_delay_seconds=30, log_prints=True)
def transform_data(xml_str: str, installed_capacity_df: pd.DataFrame) -> Dict[str, Any]:
    generation_forecast_df = entsoe_generation_parser(xml_str)

    # filter data
    generation_forecast_df = generation_forecast_df.loc[
        generation_forecast_df.index.minute == 0
    ]
    generation_type = generation_forecast_df.columns[0]

    result_df = pd.DataFrame(
        data={
            "forecast": generation_forecast_df[generation_type],
            "installed": installed_capacity_df.get(
                generation_type, default=pd.Series([0])
            ).iloc[0],
        },
        index=generation_forecast_df.index,
    )

    chart_data = []
    for index, row in result_df.iterrows():
        # only applies for mocked mode
        installed = v if (v := row["installed"]) > 0 else row["forecast"]

        percentage = int(row["forecast"] / installed * 100)
        chart_data.append(
            f"{index} | {'#'*percentage}{'_'*(100-percentage)}"
            f"  => {percentage}% ({row['forecast']}MW/{row['installed']}MW)"
        )
    return {"chart": "<br>".join(chart_data), "df": result_df, "title": generation_type}


@flow(retries=3, retry_delay_seconds=30)
def send_newsletters(data: Dict[str, Any]) -> None:
    """in this example the data won't be loaded into a database,
    but will be sent to registered users
    """
    email_server_credentials = EmailServerCredentials.load("my-email-credentials")
    users: List[User] = get_users()

    for user in users:
        line1 = f"Hello {user.name}, <br>"
        line2 = "Please find our lastest update on: <br><br>"
        line3 = f"<h1>Intraday Generation (Forecasts) and  Installed Capacity for Generation Type: {data['title']}</h1>"
        # this is a prefect task:
        email_send_message.with_options(name="send-user-newsletter").submit(
            email_server_credentials=email_server_credentials,
            subject=f"Newsletter: Intraday Generation: {data['title']}",
            msg=line1
            + line2
            + line3
            + data["chart"]
            + "<br><br>"
            + data["df"].to_html(),
            email_to=user.email,
        )


@flow
def data_flow(event_msg: str) -> None:
    event_payload = extract_event_payload(event_msg)
    installed_capacity = extract_installed_capacity()
    data = transform_data(event_payload, installed_capacity)
    send_newsletters(data)


if __name__ == "__main__":
    DeployModes = Enum(
        "DeployModes",
        [
            "LOCAL_TEST",
            "LOCAL_DOCKER_TEST",
            "ECS_PUSH_WORK_POOL",
        ],
    )

    ### Set your preferred flow run/ deployment mode here:
    deploy_mode = DeployModes.ECS_PUSH_WORK_POOL

    if deploy_mode == DeployModes.LOCAL_TEST:
        # test flow with mocked event data
        #  and run it locally without deployment:
        data_flow(mock_event_data())

    else:
        import os
        from dotenv import load_dotenv
        from prefect.deployments.runner import DeploymentImage
        from prefect.flows import DeploymentTrigger

        cfd = pathlib.Path(__file__).parent

        load_dotenv(override=True)

        job_variables: Dict[str, Any] | None = None
        triggers: List[DeploymentTrigger] | None = None

        if deploy_mode == DeployModes.LOCAL_DOCKER_TEST:
            # test flow docker deployment locally and initiate quick run in prefect cloud ui:
            name = "local-docker-test"
            push = False
            work_pool_name = "newsletter_docker_workpool"

        elif deploy_mode == DeployModes.ECS_PUSH_WORK_POOL:
            # provision work pool with information about your AWS infrastructure
            job_variables = {
                "execution_role_arn": os.getenv("EXECUTION_ROLE", ""),
                "task_role_arn": os.getenv("TASK_ROLE", ""),
                "cluster": os.getenv("ECS_CLUSTER"),
                "vpc_id": os.getenv("VPC_ID", ""),
                "container_name": os.getenv("ECR_REPO_NAME", ""),
                "family": "prefect-flow",  # newsletter
                "aws_credentials": {
                    "$ref": {
                        "block_document_id": os.getenv("AWS_CREDENTIAL_BLOCK_ID", "")
                    }
                },
            }
            # create an automation, you may want to rename the corresponding webhook:
            triggers = [
                DeploymentTrigger(
                    match={"prefect.resource.id": "entsoe-msg-webhook-id"},
                    parameters={"event_msg": "{{ event.payload.body }}"},
                )
            ]
            name = os.getenv("ECR_REPO_URL", "")
            push = True
            work_pool_name = "air-to-air_push"
            # note the following deployment procedure (same as in gh action):
            # 1: go into infrastructure folder and execute command: pulumi up
            # 2: put pulumi output to .env file
            # 3: authenticate to aws ecr before executing the deployment:
            #    replace: aws_account_id and region
            #    aws ecr get-login-password --region region | docker login --username AWS --password-stdin aws_account_id.dkr.ecr.region.amazonaws.com

        data_flow.deploy(
            "deploy_dataflow_air-to-air_push-infra-loc",
            work_pool_name=work_pool_name,
            job_variables=job_variables,
            image=DeploymentImage(
                name=name,
                tag=os.getenv("IMAGE_TAG"),
                dockerfile=cfd / "Dockerfile",
            ),
            build=True,
            push=push,
            triggers=triggers,
        )
