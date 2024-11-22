from app.helpers.authenticate import jwt_required
from mlflow.tracking import MlflowClient
from flask_restful import Resource, request
from app.schemas.experiments import ExperimentsSchema
import marshmallow
from types import SimpleNamespace


class ExperimentView(Resource):
    def __init__(self):
        self.client = MlflowClient("https://mlflow.renu-01.cranecloud.io")

    @jwt_required
    def get(self, current_user):
        # Retrieve all experiments
        name = request.args.get('name', None)
        if name:
            experiments = self.client.search_experiments(
                filter_string=f"name LIKE '%{name}%'")
        else:
            experiments = self.client.search_experiments()

        return {"status": "success", "data": [{"experiment_id": exp.experiment_id, "name": exp.name} for exp in experiments]}


class ExperimenDetailView(Resource):
    def __init__(self):
        self.client = MlflowClient("https://mlflow.renu-01.cranecloud.io")

    @jwt_required
    def get(self):
        # Retrieve from the user's saved experiment ids
        pass

    @jwt_required
    def get(self, experiment_id, current_user):
        # Retrieve a single experiment by ID
        try:
            experiment = self.client.get_experiment(experiment_id)
            return {
                "status": "success",
                "data": {
                    "experiment_id": experiment.experiment_id,
                    "name": experiment.name,
                    "artifact_location": experiment.artifact_location,
                    "lifecycle_stage": experiment.lifecycle_stage,
                    "tags": experiment.tags
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

    @jwt_required
    def patch(self, experiment_id, current_user):
        # Update experiment details
        experiments_schema = ExperimentsSchema()
        try:
            validated_data = experiments_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400

        experiment_data = SimpleNamespace(**validated_data)

        try:
            if experiment_data.name:
                self.client.rename_experiment(
                    experiment_id, experiment_data.name)
            # if experiment_data.tags:
            #     self.client.set_experiment_tag(experiment_id, experiment_data.tags)

            return {"status": "success", "message": "Experiment updated successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

    @jwt_required
    def delete(self, experiment_id, current_user):
        # Delete an experiment
        try:
            self.client.delete_experiment(experiment_id)
            return {"status": "success", "message": "Experiment deleted successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400


class ExperimentRunsView(Resource):
    def __init__(self):
        self.client = MlflowClient("https://mlflow.renu-01.cranecloud.io")

    @jwt_required
    def get(self, experiment_id, current_user):
        # Get all runs for an experiment
        max_results = request.args.get('max_results', 100, type=int)

        try:
            runs = self.client.search_runs(
                experiment_ids=[experiment_id],
                max_results=max_results,
            )
            return {
                "status": "success",
                "data": [{
                    "run_id": run.info.run_id,
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "metrics": run.data.metrics,
                    "params": run.data.params,
                    "tags": run.data.tags
                } for run in runs]
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404
