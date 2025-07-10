from pymongo import MongoClient

# Replace this with your Atlas URI
MONGO_URI = "mongodb+srv://ordersDbAdmin:LuiQu4KLLM0KXvQX@orders-cluster.jbais.mongodb.net/?retryWrites=true&w=majority&appName=orders-cluster"

client = MongoClient(MONGO_URI)

