from types import SimpleNamespace
from app.helpers.kube import create_kube_clients, deploy_user_app
from flask_restful import Resource, request
from app.schemas.app import AppDeploySchema
from mlflow.tracking import MlflowClient
from app.helpers.authenticate import (
    jwt_required
)
from mlflow.exceptions import MlflowException
import marshmallow


class AppsView(Resource):
    @jwt_required
    def post(self, current_user):
        app_schema = AppDeploySchema()

        try:
            validated_data = app_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400
        if validated_data.get('is_modal') and not (validated_data.get('model_image_uri') or validated_data.get('mlflow_artifact_uri')):
            return dict(status="error", message="Missing data for required field, model_image_uri"), 400
        if validated_data.get('is_modal') and not validated_data.get('model_server'):
            return dict(status="error", message="Missing data for required field, model_server"), 400

        is_mlflow = validated_data.get('is_mlflow')
        mlflow_artifact_uri = validated_data.get('mlflow_artifact_uri')
        if (is_mlflow and not mlflow_artifact_uri) or (mlflow_artifact_uri and not is_mlflow):
            return dict(status="error", message="Both is_mlflow and mlflow_artifact_uri must be provided together."), 400
        
        # artifact verification
        if is_mlflow and mlflow_artifact_uri:
            try:
                client = MlflowClient()
                # Extract the run ID and artifact path from the URI
                if not mlflow_artifact_uri.startswith("runs:/"):
                    return dict(status="error", message="Invalid MLflow artifact URI format."), 400

                run_id, artifact_path = mlflow_artifact_uri.replace("runs:/", "").split("/", 1)

                # Check if the run exists
                run = client.get_run(run_id)
                if not run:
                    return dict(status="error", message=f"Run ID {run_id} does not exist."), 404

                # Check if the artifact exists
                artifacts = client.list_artifacts(run_id)
                artifact_exists = any(artifact.path == artifact_path for artifact in artifacts)
                if not artifact_exists:
                    return dict(status="error", message=f"Artifact {artifact_path} does not exist in run {run_id}."), 404

            except MlflowException as e:
                return dict(status="error", message=f"MLflow error: {str(e)}"), 500
            except Exception as e:
                return dict(status="error", message=f"Unexpected error: {str(e)}"), 500


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
        # print(current_user)
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")
