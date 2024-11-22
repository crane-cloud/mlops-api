from app.helpers.mlflow_service import get_run_json_object, get_mlflow_client
from flask_restful import Resource, request
from app.helpers.authenticate import jwt_required
from mlflow.tracking import MlflowClient
import mlflow
from app.schemas.runs import RunsSchema
from types import SimpleNamespace
import marshmallow


class ExperimentRunsView(Resource):
    @jwt_required
    def get(self, experiment_id, current_user):
        """ Get all runs for an experiment """
        max_results = request.args.get('max_results', 100, type=int)

        try:
            runs = get_mlflow_client().search_runs(
                experiment_ids=[experiment_id],
                max_results=max_results,
            )
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

        return {"status": "success",
                "data": [get_run_json_object(run) for run in runs]}


class RunDetailView(Resource):

    @jwt_required
    def get(self, run_id, current_user):
        """ Get run details """
        try:
            run = get_mlflow_client().get_run(run_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

        return {
            "status": "success",
            "data": get_run_json_object(run, full=True)
        }

    @jwt_required
    def patch(self, run_id, current_user):
        """ Update run details """
        runs_schema = RunsSchema()
        try:
            validated_data = runs_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400

        runs_data = SimpleNamespace(**validated_data)

        try:
            if runs_data.status:
                get_mlflow_client().set_terminated(run_id, runs_data.status)
            if runs_data.status:
                get_mlflow_client().set_tag(
                    run_id, "mlflow.runName", runs_data.run_name)

        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Run updated successfully"}

    @jwt_required
    def delete(self, run_id, current_user):
        """ Delete a run """
        try:
            get_mlflow_client().delete_run(run_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Run deleted successfully"}
