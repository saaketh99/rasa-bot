from pymongo import MongoClient

client = MongoClient("mongodb+srv://ordersDbAdmin:LuiQu4KLLM0KXvQX@orders-cluster.jbais.mongodb.net/?retryWrites=true&w=majority&appName=orders-cluster")
db = client["orders-db"]  
sessions_collection = db["user_sessions"] 
