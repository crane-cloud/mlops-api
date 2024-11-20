from types import SimpleNamespace
from app.helpers.kube import create_kube_clients, deploy_user_app
from flask_restful import Resource, request
from app.schemas.app import AppDeploySchema
from app.helpers.authenticate import (
    jwt_required
)
import marshmallow


class AppsView(Resource):
    @jwt_required
    def post(self, current_user):
        app_schema = AppDeploySchema()

        try:
            validated_data = app_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400

        namepaced_data = SimpleNamespace(**validated_data)
        namepaced_data.cluster = SimpleNamespace(**namepaced_data.cluster)
        namepaced_data.project = SimpleNamespace(**namepaced_data.project)

        # deploy notebook
        kube_client = create_kube_clients(
            kube_host=namepaced_data.cluster.host,
            kube_token=namepaced_data.cluster.token
        )
        # return True
        new_app = deploy_user_app(kube_client=kube_client, project=namepaced_data.project,
                                  cluster=namepaced_data.cluster, app_data=validated_data)
        if type(new_app) == SimpleNamespace and hasattr(new_app, 'status_code'):
            return dict(status="error", message=new_app.message), new_app.status_code

        return dict(status="success", app=vars(new_app)), 201

    @jwt_required
    def get(self, current_user):
        print(current_user)
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")
