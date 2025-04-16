from mlflow.tracking import MlflowClient
from mlflow.exceptions import MlflowException
import json


def get_mlflow_client(current_app):
    return MlflowClient(current_app.config['MLFLOW_TRACKING_URI'])


def get_mlflow_experiments(client, name=None):
    if name:
        return client.search_experiments(filter_string=f"name LIKE '%{name}%'")
    else:
        return client.search_experiments()


def get_experiment_json_object(experiment):
    return {
        "experiment_id": experiment.experiment_id,
        "name": experiment.name,
        "artifact_location": experiment.artifact_location,
        "creation_time": experiment.creation_time,
        "last_update_time": experiment.last_update_time,
        "lifecycle_stage": experiment.lifecycle_stage,
        "tags": experiment.tags
    }

def safe_serialize(obj):
    """Recursively serializes objects, converting non-serializable types to strings."""
    if isinstance(obj, (int, float, str, bool, type(None))):  
        return obj  # Basic

    if isinstance(obj, dict):  
        return {key: safe_serialize(value) for key, value in obj.items()}  # For serialize dicts

    if isinstance(obj, list) or isinstance(obj, tuple):  
        return [safe_serialize(item) for item in obj]  # For lists and tuples

    try:
        return json.loads(json.dumps(obj))  
    except (TypeError, OverflowError):
        return str(obj)  # Fallback: Convert to string representation if it can't be serialized

def get_run_json_object(run, full=False):
    if full:
        return safe_serialize(run.to_dictionary())

    run_info = {
        "run_id": run.info.run_id,
        "status": run.info.status,
        "start_time": run.info.start_time,
        "end_time": run.info.end_time,
        "artifact_uri": run.info.artifact_uri,
        "run_name": run.info.run_name,
        "user_id": run.info.user_id,
        "experiment_id": run.info.experiment_id,
    }

    return safe_serialize(run_info)




def validate_mlflow_artifact(mlflow_artifact_uri):
   
    try:
        client = MlflowClient()

        # Validate the artifact URI format
        if not mlflow_artifact_uri.startswith("runs:/"):
            return {"status": "error", "message": "Invalid MLflow artifact URI format."}, 400

        # Extract run ID and artifact path
        try:
            run_id, artifact_path = mlflow_artifact_uri.replace("runs:/", "", 1).split("/", 1)
        except ValueError:
            return {"status": "error", "message": "Malformed MLflow artifact URI."}, 400

        # Validate run existence
        try:
            client.get_run(run_id)
        except MlflowException:
            return {"status": "error", "message": f"Run ID '{run_id}' does not exist."}, 404

        # Validate artifact existence
        artifacts = client.list_artifacts(run_id)
        if not any(artifact.path == artifact_path for artifact in artifacts):
            return {"status": "error", "message": f"Artifact '{artifact_path}' does not exist in run '{run_id}'."}, 404

        return mlflow_artifact_uri

    except MlflowException as e:
        return {"status": "error", "message": f"MLflow error: {str(e)}"}, 500
    except Exception as e:
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}, 500
