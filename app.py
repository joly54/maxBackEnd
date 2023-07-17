import os
import os.path as op

from flask import Flask, send_from_directory, request
from flask_admin import Admin
from flask_admin.contrib.fileadmin import FileAdmin
from flask_admin.contrib.sqla import ModelView
from flask_cors import CORS
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from flasgger import Swagger


app = Flask(__name__)
swagger = Swagger(app)
CORS(app, supports_credentials=True)
api = Api(app)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///base.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = "secretkey"
db = SQLAlchemy(app)
admin = Admin(app, template_mode='bootstrap4', name='Vin-cinema')
path = op.join(op.dirname(__file__), 'static')
admin.add_view(FileAdmin(path, '/static/', name='File Management'))
base_url = "http://127.0.0.1:5000/"


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80))
    price = db.Column(db.Integer)
    description = db.Column(db.String(200))
    image = db.Column(db.String(200))
    category = db.Column(db.String(200))

    def __repr__(self):
        return '<Product %r>' % self.name
admin.add_view(ModelView(Product, db.session))


@app.route('/files/<path:path>')
def send_static_files(path):
    return send_from_directory('', path)

class FillDB(Resource):
    def get(self):
        imgs = os.listdir('static')
        for img in imgs:
            new_product = Product(name=img, price=100, description='description', image=base_url + "static/" + img,
                                  category='category')
            db.session.add(new_product)
            db.session.commit()
        return {'result': 'success'}


class Products(Resource):
    def get(self):
        """
                ---
                tags:
                  - Products
                parameters:
                  - name: page
                    in: query
                    type: integer
                    description: Page number
                  - name: size
                    in: query
                    type: integer
                    description: Number of items per page
                responses:
                  200:
                    description: List of products
                """
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 10))
        products = Product.query.paginate(page=page, per_page=size).items
        serialized_products = []
        for product in products:
            serialized_product = {
                'id': product.id,
                'name': product.name,
                'price': product.price,
                "description": product.description,
                "image": product.image,
            }
            serialized_products.append(serialized_product)

        return {'products': serialized_products}


class GetProduct(Resource):
    def get(self, id):
        """
           ---
           tags:
             - Products
           parameters:
             - name: id
               in: path
               type: integer
               required: true
               description: Product ID
           responses:
             200:
               description: Product details
             404:
               description: Product not found
           """
        product = Product.query.filter_by(id=id).first()
        if product is None:
            return {'product': None}, 404

        serialized_product = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            "description": product.description,
            "image": product.image,
        }

        return {'product': serialized_product}


api.add_resource(FillDB, '/filldb')
api.add_resource(Products, '/products')
api.add_resource(GetProduct, '/product/<int:id>')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
