from app.helpers.mlflow_service import get_run_json_object, get_mlflow_client
from flask_restful import Resource
from flask import send_file
from app.helpers.authenticate import jwt_required
from mlflow.tracking import MlflowClient
import mlflow
from app.schemas.runs import RunsSchema
from types import SimpleNamespace
from mlflow.artifacts import download_artifacts
import os
import shutil
import tempfile


class ArtifactsView(Resource):
    @jwt_required
    def get(self, experiment_id, current_user):
        try:
            # lists artifacts for all runs in the experiment, it aids in display and download of the artifacts
            client = MlflowClient()
            runs = client.search_runs(experiment_ids=[experiment_id])
            artifacts = []
            for run in runs:
                run_id = run.info.run_id
                run_name = run.data.tags.get("mlflow.runName", "Unnamed Run")
                for artifact in client.list_artifacts(run_id):
                    artifact_info = {
                        "path": artifact.path,
                        "url":  mlflow.get_artifact_uri(artifact.path),
                        "run_id": run_id,
                        "run_name": run_name
                    }
                    artifacts.append(artifact_info)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

        return {"status": "success", "data": artifacts}
    

class ArtifactDownloadView(Resource):
    @jwt_required
    def get(self, experiment_id, run_id, artifact_path, current_user):
        try:
            local_path = download_artifacts(run_id=run_id, artifact_path=artifact_path)

            if local_path:
                temp_dir = tempfile.mkdtemp()
                base_name = os.path.join(temp_dir, os.path.basename(local_path))
                # shutil.make_archive creates a zip file
                zip_path = shutil.make_archive(base_name, 'zip', local_path)
                return send_file(zip_path, as_attachment=True)
            else:
                return {"status": "error", "message": "Failed to download artifact"}, 404
            
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

    
         