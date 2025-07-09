from pymongo import MongoClient

client = MongoClient("mongodb+srv:ordersDbAdmin:LuiQu4KLLM0KXvQX//@orders-cluster.jbais.mongodb.net/")
db = client["orders-db"]  # You can name this whatever you want
sessions_collection = db["user_sessions"]  # This is your “file” or table-like collection
