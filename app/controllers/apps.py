from types import SimpleNamespace
from app.helpers.kube import create_kube_clients, deploy_user_app
from flask_restful import Resource, request
from app.schemas.app import AppDeploySchema
from app.helpers.mlflow_service import validate_mlflow_artifact
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
        if validated_data.get('is_modal') and not validated_data.get('model_image_uri'):
            return dict(status="error", message="Missing data for required field, model_image_uri"), 400
        if validated_data.get('is_modal') and not validated_data.get('model_server'):
            return dict(status="error", message="Missing data for required field, model_server"), 400

        if (validated_data.get('is_modal') and validated_data.get('model_server') == "MLFLOW_SERVER"):
            validation_result = validate_mlflow_artifact(
                validated_data['model_image_uri'])
            if isinstance(validation_result, tuple):
                error_body, status_code = validation_result
                return dict(status="error", message=error_body.get("message", "Validation failed.")), status_code
        if (validated_data.get('is_modal') and validated_data.get('model_server') == "HUGGINGFACE_SERVER"):
            if not validated_data.get('task'):
                return dict(status="error", message="Missing data for required field, task for Huggingface model"), 400
        namepaced_data = SimpleNamespace(**validated_data)
        namepaced_data.cluster = SimpleNamespace(**namepaced_data.cluster)
        namepaced_data.project = SimpleNamespace(**namepaced_data.project)

        # deploy notebook
        kube_client = create_kube_clients(
            kube_host=namepaced_data.cluster.host,
            kube_token=namepaced_data.cluster.token
        )

        new_app = deploy_user_app(kube_client=kube_client, project=namepaced_data.project,
                                  cluster=namepaced_data.cluster, app_data=validated_data)
        if type(new_app) == SimpleNamespace and hasattr(new_app, 'status_code'):
            return dict(status="error", message=new_app.message), new_app.status_code

        return dict(status="success", app=vars(new_app)), 201

    @jwt_required
    def get(self, current_user):
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")
