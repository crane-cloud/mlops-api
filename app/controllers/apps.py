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
        app_schema = AppDeploySchema(unknown=marshmallow.EXCLUDE)
        try:
            validated_data = app_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400
        # deploy notebook
        # kube_client = create_kube_clients(
        #     kube_host=validated_data.cluster.kube_host,
        #     kube_token=validated_data.cluster.kube_token
        # )
        # new_app = deploy_user_app(kube_client=kube_client, project=validated_data.project,
        #                           cluster=validated_data.cluster, app_data=validated_data)
        # print(new_app)

        return dict(status="success", message=validated_data)

    @jwt_required
    def get(self, current_user):
        print(current_user)
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")
