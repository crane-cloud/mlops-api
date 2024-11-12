from flask_restful import Api
from app.controllers import (IndexView, AppsView)

api = Api()

# Index route
api.add_resource(IndexView, '/')

# Apps route
api.add_resource(AppsView, '/apps')
