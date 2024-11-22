from flask_restful import Api
from app.controllers import (
    IndexView, AppsView, ExperimentRunsView, ExperimentView, RunView, ExperimenDetailView)

api = Api()

# Index route
api.add_resource(IndexView, '/')

# Apps route
api.add_resource(AppsView, '/apps')

api.add_resource(ExperimentView, '/experiments')
api.add_resource(ExperimenDetailView, '/experiments/<experiment_id>')
api.add_resource(ExperimentRunsView, '/experiments/<experiment_id>/runs')
api.add_resource(RunView, '/run/<run_id>')
