from flask import Flask  
from flask_restful import Resource, Api  
from flask_restful import reqparse  

import imp

app = Flask(__name__)  
api = Api(app)

class Prediction(Resource):
    def get(self):

        parser = reqparse.RequestParser()
        parser.add_argument('longitude', type=float, 
                 help='longitude cannot be converted')
        parser.add_argument('latitude', type=float, 
                 help='latitude cannot be converted')
        args = parser.parse_args()
        
        model = imp.load_source('model', 'model.py')

        prediction = model.predict([
                args['longitude'], 
                args['latitude'],
            ])

        print "THE PREDICTION IS: " + str(prediction)

        return {
                'longitude': args['longitude'],
                'latitude': args['latitude'],
                'predicted_price': prediction
               }

api.add_resource(Prediction, '/prediction')

if __name__ == '__main__':  
    app.run(debug=False)
