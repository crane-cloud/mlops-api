from mlflow.tracking import MlflowClient

CLIENT_URL = "https://mlflow.renu-01.cranecloud.io"


def get_mlflow_client():
    return MlflowClient(CLIENT_URL)


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


def get_run_json_object(run, full=False):
    if full:
        return run.to_dictionary()
    return {
        "run_id": run.info.run_id,
        "status": run.info.status,
        "start_time": run.info.start_time,
        "end_time": run.info.end_time,
        "artifact_uri": run.info.artifact_uri,
        "run_name": run.info.run_name,
        "user_id": run.info.user_id,
        "experiment_id": run.info.experiment_id,
    }
