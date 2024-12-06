from app.helpers.authenticate import jwt_required
from app.helpers.mlflow_service import get_mlflow_experiments, get_mlflow_client, get_experiment_json_object
from flask_restful import Resource, request
from app.schemas.experiments import ExperimentsSchema, UserExperimentsSchema
from app.models.user_experiments import UserExperiments
import marshmallow
from types import SimpleNamespace
import json


class ExperimentView(Resource):

    @jwt_required
    def get(self, current_user):
       
        mlflow_client = get_mlflow_client()  # Initialize the MLflow client
        app_id = request.args.get('app_id') 

        if not app_id:
            return {"status": "error", "message": "Missing 'app_id' parameter."}, 400

        try:
            
            user_experiments_schema = UserExperimentsSchema(many=True)

            experiments = UserExperiments.find_many_by_filters(app_id=app_id.strip())

            validated_data = user_experiments_schema.dumps(experiments)
            experiments_data_list = json.loads(validated_data)


            if not experiments_data_list:
                return {"status": "success", "data": []}, 200  

            
            experiment_data = []
            for ue in experiments_data_list:
                print(ue)
                try:
                    mlflow_experiment = mlflow_client.get_experiment(ue['experiment_id'])
                    experiment_data.append(get_experiment_json_object(mlflow_experiment))
                except Exception as e: 
                    experiment_data.append(
                        {"experiment_id": ue.experiment_id, "error": str(e)}
                    )

            return {"status": "success", "data": experiment_data}, 200

        except Exception as e:
            return {"status": "error", "message": str(e)}, 500


class ExperimentDetailView(Resource):

    @jwt_required
    def get(self, experiment_id, current_user):
        """ Retrieve a single experiment by ID """
        try:
            experiment = get_mlflow_client().get_experiment(experiment_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

        return {"status": "success",
                "data": get_experiment_json_object(experiment)}

    @jwt_required
    def patch(self, experiment_id, current_user):
        """ Update experiment details """
        experiments_schema = ExperimentsSchema()
        try:
            validated_data = experiments_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400

        experiment_data = SimpleNamespace(**validated_data)

        try:
            if experiment_data.name:
                get_mlflow_client().rename_experiment(
                    experiment_id, experiment_data.name)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Experiment updated successfully"}

    @jwt_required
    def delete(self, experiment_id, current_user):
        """ Delete an experiment """
        try:
            get_mlflow_client().delete_experiment(experiment_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Experiment deleted successfully"}
