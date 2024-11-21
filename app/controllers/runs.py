from flask_restful import Resource, request
from app.helpers.authenticate import jwt_required
from mlflow.tracking import MlflowClient
import mlflow
from app.schemas.runs import RunsSchema
from types import SimpleNamespace
import marshmallow

class RunView(Resource):
    def __init__(self):
        self.client = MlflowClient("https://mlflow.renu-01.cranecloud.io")
    
    @jwt_required
    def get(self, run_id):
        #Get a specific run
        try:
            run = self.client.get_run(run_id)
            return {
                "status": "success",
                "data": {
                    "run_id": run.info.run_id,
                    "status": run.info.status,
                    "start_time": run.info.start_time,
                    "end_time": run.info.end_time,
                    "metrics": run.data.metrics,
                    "params": run.data.params,
                    "tags": run.data.tags
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

    @jwt_required
    def patch(self, run_id):
        #Update run details
        runs_schema = RunsSchema()
        try:
            validated_data = runs_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400
        
        runs_data = SimpleNamespace(**validated_data)

        try:
            if runs_data.status:
                self.client.set_terminated(run_id, runs_data.status)
            if runs_data.status:
                self.client.set_tag(run_id, "mlflow.runName", runs_data.run_name)

            return {"status": "success", "message": "Run updated successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

    @jwt_required
    def delete(self, run_id):
        #Delete a run
        try:
            self.client.delete_run(run_id)
            return {"status": "success", "message": "Run deleted successfully"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400
