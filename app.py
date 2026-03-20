import os
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from minio import Minio

app = Flask(__name__)

# --- FIX: Use the exact key 'SQLALCHEMY_DATABASE_URI' ---
# If running inside Docker, use the path mapped in the volume
if os.path.exists("/mnt/block_volume"):
    BLOCK_STORAGE_PATH = "/mnt/block_volume/ecommerce.db"
else:
    # Running locally on Windows
    BLOCK_STORAGE_PATH = os.path.join(os.getcwd(), "my_block_data", "ecommerce.db")

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{BLOCK_STORAGE_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- FIX: Pull credentials from environment variables ---
minio_client = Minio(
    os.getenv("MINIO_ENDPOINT", "localhost:9000"),
    access_key=os.getenv("MINIO_ROOT_USER", "admin_user"),
    secret_key=os.getenv("MINIO_ROOT_PASSWORD", "admin_password"),
    secure=False
)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    price = db.Column(db.Float, nullable=False)
    image_name = db.Column(db.String(120))

@app.route('/')
def home():
    return "E-commerce Lab is Running! Send a POST request to /product to add data."

@app.route('/product', methods=['POST'])
def add_product():
    name = request.form.get('name')
    price = request.form.get('price')
    image = request.files.get('image')

    if not image:
        return jsonify({"error": "No image uploaded"}), 400

    # 1. Save file locally first so MinIO can find it
    temp_path = image.filename
    image.save(temp_path)

    try:
        # 2. Object Storage Action (MinIO)
        bucket = "cs111"
        if not minio_client.bucket_exists(bucket):
            minio_client.make_bucket(bucket)
        
        # FIX: fput_object(bucket_name, object_name, file_path)
        minio_client.fput_object(bucket, image.filename, temp_path)

        # 3. Block Storage Action (Database)
        # Removed 'metadata' because it's not in your Product class
        new_product = Product(name=name, price=price, image_name=image.filename)
        db.session.add(new_product)
        db.session.commit()

    finally:
        # Clean up the local file
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return jsonify({"status": "success", "msg": "Structured data in Block, Image in Object"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    print("Starting Flask app on http://0.0.0.0:5000")
    app.run(host='0.0.0.0', port=5000) # host='0.0.0.0' is required for Docker
