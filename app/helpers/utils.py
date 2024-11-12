import requests
import os
import datetime
from app.schemas import MetricsSchema
from types import SimpleNamespace

PRODUCT_BASE_URL = os.getenv('PRODUCT_BASE_URL')
PROJECT_ENDPOINT = f"{PRODUCT_BASE_URL}/projects"
APP_ENDPOINT = f"{PRODUCT_BASE_URL}/apps"


def get_project_data(request):
    project_query_data = request.get_json()

    metric_schema = MetricsSchema()
    validated_query_data = metric_schema.load(
        project_query_data)

    # if errors:
    #     return dict(status='fail', message=errors), 400

    current_time = datetime.datetime.now()
    yesterday_time = current_time + datetime.timedelta(days=-1)

    start = validated_query_data.get('start', yesterday_time.timestamp())
    end = validated_query_data.get('end', current_time.timestamp())
    step = validated_query_data.get('step', '1h')
    project_id = validated_query_data.get('project_id', '')
    project_name = validated_query_data.get('project_name', '')
    prometheus_url = validated_query_data.get('prometheus_url', '')

    if not project_id and not project_name:
        return SimpleNamespace(status='failed', message="project_id or project_name is required", status_code=400)

    if project_name and not prometheus_url:
        return SimpleNamespace(status='fail', message='Please add a prometheus_url', status_code=404)

    if not project_name:
        project_response = requests.get(
            f"{PROJECT_ENDPOINT}/{project_id}", headers={
                "accept": "application/json",
                "Authorization": request.headers.get('Authorization')
            })
        if not project_response.ok:
            return SimpleNamespace(status='failed', message="Failed to fetch project for current user", status_code=400)

        project_response = project_response.json()
        project_data = project_response['data']['project']
        project_name = project_data.get('alias', '')
        prometheus_url = project_data.get('prometheus_url', '')

    if not prometheus_url:
        return SimpleNamespace(status='fail', message='No prometheus url available on the project', status_code=404)

    os.environ["PROMETHEUS_URL"] = prometheus_url
    return SimpleNamespace(
        start=start,
        end=end,
        step=step,
        namespace=project_name,
        status_code=200
    )


def get_app_data(request):
    app_query_data = request.get_json()

    metric_schema = MetricsSchema()
    validated_query_data = metric_schema.load(
        app_query_data)

    app_name = validated_query_data.get('app_name', '')
    app_id = validated_query_data.get('app_id', '')

    if not app_id and not app_name:
        return SimpleNamespace(status='failed', message="app_id or app_name is required", status_code=400)

    project_data = get_project_data(request)
    if project_data.status_code != 200:
        return dict(status='fail', message=project_data.message), project_data.status_code

    # if errors:
    #   return dict(status='fail', message=errors), 400

    if not app_name:
        # get app details
        app_response = requests.get(
            f"{APP_ENDPOINT}/{app_id}", headers={
                "accept": "application/json",
                "Authorization": request.headers.get('Authorization')
            }
        )

        if not app_response.ok:
            return SimpleNamespace(status='failed', message="Failed to fetch app for current user", status_code=400)

        app_response = app_response.json()
        app_data = app_response['data']['apps']
        app_name = app_data['alias']

    return SimpleNamespace(
        start=project_data.start,
        end=project_data.end,
        step=project_data.step,
        app_alias=app_name,
        namespace=project_data.namespace,
        status_code=200
    )
