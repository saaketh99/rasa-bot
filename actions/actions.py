import os
import re
import time
from typing import Any, Text, Dict, List, Optional, Tuple
from dateutil import parser
import pandas as pd
import matplotlib.pyplot as plt
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from rapidfuzz import process, fuzz
from datetime import datetime, timedelta
from collections import Counter, defaultdict
from bson.regex import Regex
import pytz

# --- DATABASE CONNECTION ---
# It's good practice to use environment variables for credentials in production
DB_URI = "mongodb+srv://ordersDbReader:7HFtko7GNplIIi11@orders-flex-cluster.wbz5pht.mongodb.net/?w=majority&appName=orders-flex-cluster"
try:
    client = MongoClient(DB_URI, serverSelectionTimeoutMS=5000)
    db = client["orders-db"]
    collection = db["SaaS_Orders"]
    # The ismaster command is cheap and does not require auth, used to check connection.
    client.admin.command('ismaster')
    print("SUCCESS: MongoDB connection established.")
except Exception as e:
    print(f"FATAL: Could not connect to MongoDB. Actions will fail. Error: {e}")
    collection = None

# --- GLOBAL HELPERS & DATA ---
def load_initial_data():
    # THE FIX IS APPLIED HERE
    if collection is None: return [], []
    try:
        sender_cities = collection.distinct("start.address.mapData.city")
        receiver_cities = collection.distinct("end.address.mapData.city")
        known_cities = list(set(filter(None, sender_cities + receiver_cities)))
        known_statuses = list(set(filter(None, collection.distinct("orderStatus"))))
        return known_cities, known_statuses
    except Exception as e:
        print(f"Warning: Could not load initial data from DB: {e}")
        return [], []

known_cities, known_statuses = load_initial_data()


# --- UTILITY FUNCTIONS ---

def fuzzy_city_match(city_name, known_cities_list, min_score=70):
    if not city_name or not known_cities_list: return None
    match = process.extractOne(city_name.strip(), known_cities_list, scorer=fuzz.token_sort_ratio)
    return match[0] if match and match[1] >= min_score else None

def extract_pickup_city(text: str) -> Optional[str]:
    text_lower = text.lower()
    match = re.search(r'\bfrom\s+([\w\s]+?)(?:\s+to\b|$)', text_lower)
    if match:
        return fuzzy_city_match(match.group(1), known_cities)
    return None

def extract_destination_city(text: str) -> Optional[str]:
    text_lower = text.lower()
    match = re.search(r'\bto\s+([\w\s]+)', text_lower)
    if match:
        return fuzzy_city_match(match.group(1), known_cities)
    return None

def extract_dates_from_text(text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    text = text.lower().replace("–", "-").replace(" to ", " - ").replace("between ", "")
    date_patterns = re.findall(r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})", text)
    try:
        start_date = parser.parse(date_patterns[0])
        end_date = parser.parse(date_patterns[1])
        return start_date, end_date
    except Exception:
        return None, None

def serialize_for_json(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(obj, (list, tuple)):
        return [serialize_for_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    return obj

def create_excel_file(rows, filename_prefix):
    """A centralized function to create and save an Excel file."""
    if not rows: return None
    
    df = pd.DataFrame(rows)
    for col in df.select_dtypes(include=['datetime64[ns, UTC]', 'datetime64[ns]', 'datetimetz']).columns:
        df[col] = df[col].dt.strftime('%Y-%m-%d %H:%M:%S')

    safe_prefix = re.sub(r'\W+', '_', filename_prefix)
    timestamp = datetime.now().strftime('%Y%m%d%H%M')
    filename = f"{safe_prefix}_{timestamp}.xlsx"
    
    os.makedirs("static/files", exist_ok=True)
    filepath = os.path.join("static/files", filename)
    df.to_excel(filepath, index=False)
    
    public_url = f"http://51.20.18.59:8080/static/files/{filename}"
    return public_url

# --- RASA ACTIONS ---
# THE FIX IS APPLIED TO EVERY ACTION BELOW (if collection is None:)

class ActionCxOrder(Action):
    def name(self) -> Text:
        return "action_cx_date"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]
        
        # ... (rest of the function is the same)
        customer_input = tracker.get_slot("customer_name")
        s_date, e_date = extract_dates_from_text(tracker.latest_message.get("text", ""))

        if not all([customer_input, s_date, e_date]):
            dispatcher.utter_message("Please provide a customer name and a full date range (e.g., 'orders for Ola from 2023-01-01 to 2023-01-31').")
            return []

        query = {
            "start.contact.name": {"$regex": customer_input, "$options": "i"},
            "createdAt": {"$gte": s_date, "$lt": e_date + timedelta(days=1)}
        }
        matched_orders = list(collection.find(query))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found for **{customer_input}** in the provided date range.")
            return []

        rows = [{
            "Order ID": o.get("sm_orderid", "N/A"),
            "Customer": o.get("start", {}).get("contact", {}).get("name", "Unknown"),
            "From City": o.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
            "To City": o.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
            "Created At": o.get("createdAt")
        } for o in matched_orders]

        message = f"Found **{len(rows)}** orders for **{customer_input}** from {s_date.strftime('%Y-%m-%d')} to {e_date.strftime('%Y-%m-%d')}."
        public_url = create_excel_file(rows, f"orders_{customer_input}")

        dispatcher.utter_message(
            text=message,
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionrouteOrder(Action):
    def name(self) -> Text:
        return "action_route"

    def run(self, dispatcher, tracker, domain):
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        text = tracker.latest_message.get("text", "")
        pickup_city = extract_pickup_city(text)
        drop_city = extract_destination_city(text)
        
        if not pickup_city or not drop_city:
            dispatcher.utter_message("Please provide both a pickup and a destination city (e.g., 'orders from city A to city B').")
            return []
            
        query = {
            "start.address.mapData.city": {"$regex": f"^{pickup_city}$", "$options": "i"},
            "end.address.mapData.city": {"$regex": f"^{drop_city}$", "$options": "i"}
        }
        matched_orders = list(collection.find(query))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found from **{pickup_city}** to **{drop_city}**.")
            return []

        rows = [{
            "Order ID": o.get("sm_orderid", "N/A"),
            "Sender": o.get("start", {}).get("contact", {}).get("name", "Unknown"),
            "Booking Date": o.get("createdAt")
        } for o in matched_orders]
        
        message = f"Found **{len(rows)}** orders from **{pickup_city}** to **{drop_city}**."
        public_url = create_excel_file(rows, f"orders_{pickup_city}_to_{drop_city}")

        dispatcher.utter_message(
            text=message,
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionFordestination(Action):
    def name(self) -> Text:
        return "action_cx_destination"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]
        
        customer_input = tracker.get_slot("customer_name")
        destination = extract_destination_city(tracker.latest_message.get("text", ""))

        if not customer_input or not destination:
            dispatcher.utter_message("Please provide both a customer name and a destination city.")
            return []
            
        query = {
            "start.contact.name": {"$regex": customer_input, "$options": "i"},
            "end.address.mapData.city": {"$regex": f"^{destination}$", "$options": "i"}
        }
        matched_orders = list(collection.find(query))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found for **{customer_input}** going to **{destination}**.")
            return []
            
        rows = [{
            "Order ID": o.get("sm_orderid", "N/A"),
            "Customer": o.get("start", {}).get("contact", {}).get("name", "Unknown"),
            "From City": o.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
            "Created At": o.get("createdAt")
        } for o in matched_orders]
        
        message = f"Found **{len(rows)}** orders for **{customer_input}** delivered to **{destination}**."
        public_url = create_excel_file(rows, f"orders_{customer_input}_to_{destination}")

        dispatcher.utter_message(
            text=message,
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionGetOrdersByStatus(Action):
    def name(self) -> Text:
        return "action_get_orders_by_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        message_text = tracker.latest_message.get("text", "").lower()
        
        status_mapping = {
            "pending": [s for s in known_statuses if "delivered" not in s and "cancelled" not in s],
            "delivered": [s for s in known_statuses if "delivered" in s],
            "cancelled": [s for s in known_statuses if "cancelled" in s]
        }
        
        query, status_name = {}, "matching"
        
        if any(kw in message_text for kw in ["delivered"]):
            query, status_name = {"orderStatus": {"$in": status_mapping["delivered"]}}, "delivered"
        elif any(kw in message_text for kw in ["cancelled"]):
            query, status_name = {"orderStatus": {"$in": status_mapping["cancelled"]}}, "cancelled"
        elif any(kw in message_text for kw in ["pending", "undelivered", "delayed"]):
            query, status_name = {"orderStatus": {"$in": status_mapping["pending"]}}, "pending"
        
        if not query:
            return [dispatcher.utter_message("Could not determine the status you're asking for. Please try 'pending', 'delivered', or 'cancelled'.")]

        matched_orders = list(collection.find(query))
        if not matched_orders:
            dispatcher.utter_message(f"No **{status_name}** orders found.")
            return []

        rows = [{"Order ID": o.get("sm_orderid", "N/A"), "Customer": o.get("start", {}).get("contact", {}).get("name", "Unknown"),
                 "Status": o.get("orderStatus", "Unknown"), "Date": o.get("createdAt")} for o in matched_orders]

        public_url = create_excel_file(rows, f"{status_name}_orders")
        dispatcher.utter_message(
            text=f"Found **{len(rows)}** {status_name} orders.",
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionGetOrderStatus(Action):
    def name(self) -> Text:
        return "action_get_order_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        order_id = next(tracker.get_latest_entity_values("order_id"), None)
        if not order_id: return [dispatcher.utter_message("Please provide an order ID.")]

        order = collection.find_one({"sm_orderid": order_id})
        if not order: return [dispatcher.utter_message(f"No order found with ID **{order_id}**.")]

        status = order.get("orderStatus", "Unknown")
        message = f"The status of order **{order_id}** is: **{status}**."
        
        rows = [{"Order ID": order_id, "Status": status, "Date": order.get("createdAt")}]
        
        dispatcher.utter_message(text=message, custom={"table_data": serialize_for_json(rows)})
        return []

class ActionGetOrdersByTAT(Action):
    def name(self) -> Text:
        return "action_get_orders_by_tat"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]
        
        message_text = tracker.latest_message.get("text", "").lower()
        match = re.search(r"\b(\d+)\s*days?\b", message_text)
        if not match: return [dispatcher.utter_message("Please specify the number of days for TAT.")]

        tat_days = int(match.group(1))
        
        # This remains a potentially slow query.
        delivered_orders = list(collection.find({"orderStatus": {"$regex": "delivered", "$options": "i"}}))
        matching_orders = []
        for order in delivered_orders:
            created_at = order.get("createdAt")
            delivered_at = None
            for event in order.get("orderStatusEvents", []):
                if "delivered" in event.get("status", "").lower():
                    delivered_at = event.get("timeStamp") 
                    if isinstance(delivered_at, (int, float)): delivered_at = datetime.fromtimestamp(delivered_at / 1000)
                    break
            
            if created_at and delivered_at and isinstance(created_at, datetime) and isinstance(delivered_at, datetime):
                if (delivered_at - created_at).days == tat_days:
                     matching_orders.append(order)

        if not matching_orders:
            return [dispatcher.utter_message(f"No orders found delivered in exactly **{tat_days}** days.")]

        rows = [{"Order ID": o.get("sm_orderid", "N/A"), "Customer": o.get("start",{}).get("contact",{}).get("name","Unknown"), 
                 "Booking Date": o.get("createdAt"), "TAT (days)": tat_days} for o in matching_orders]

        public_url = create_excel_file(rows, f"orders_tat_{tat_days}d")
        dispatcher.utter_message(
            text=f"Found **{len(rows)}** orders delivered in exactly **{tat_days}** days.",
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionPendingOrdersPastDays(Action):
    def name(self) -> Text:
        return "action_pending_orders_past_days"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]
        
        message_text = tracker.latest_message.get("text", "").lower()
        customer_input = tracker.get_slot("customer_name")
        match = re.search(r'(\d+)\s*days?', message_text)
        if not match: return [dispatcher.utter_message("Please specify how many past days to consider.")]
        
        n_days = int(match.group(1))
        date_cutoff = datetime.now() - timedelta(days=n_days)
        
        PENDING_STATUSES = [s for s in known_statuses if "delivered" not in s and "cancelled" not in s]
        
        query = { "orderStatus": {"$in": PENDING_STATUSES}, "createdAt": {"$gte": date_cutoff} }
        if customer_input: query["start.contact.name"] = {"$regex": customer_input, "$options": "i"}

        matched_orders = list(collection.find(query))
        
        msg_part = f"pending orders from the past **{n_days}** days"
        if customer_input: msg_part += f" for **{customer_input}**"

        if not matched_orders: return [dispatcher.utter_message(f"No {msg_part} found.")]

        rows = [{"Order ID": o.get("sm_orderid", "N/A"), "Status": o.get("orderStatus", "Unknown"),
                 "To City": o.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
                 "Created At": o.get("createdAt")} for o in matched_orders]

        public_url = create_excel_file(rows, f"pending_last_{n_days}_days")
        dispatcher.utter_message(
            text=f"Found **{len(rows)}** {msg_part}.",
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionTopPincodesByCustomer(Action):
    def name(self) -> Text:
        return "action_top_pincodes_by_customer"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]
        
        customer_input = tracker.get_slot("customer_name")
        if not customer_input: return [dispatcher.utter_message("Please provide a customer name.")]

        pipeline = [
            {"$match": {"start.contact.name": {"$regex": customer_input, "$options": "i"}}},
            {"$match": {"end.address.mapData.pincode": {"$exists": True, "$ne": ""}}},
            {"$group": {"_id": "$end.address.mapData.pincode", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        results = list(collection.aggregate(pipeline))

        if not results:
            dispatcher.utter_message(f"No destination pincodes found for **{customer_input}**.")
            return []

        rows = [{"Pincode": r["_id"], "Order Count": r["count"]} for r in results]
        message = f"Top 10 delivery pincodes for **{customer_input}**:"
        public_url = create_excel_file(rows, f"top_pincodes_{customer_input}")
        
        dispatcher.utter_message(
            text=message, 
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionOrderDetailsByID(Action):
    def name(self) -> Text:
        return "action_fetch_order_info_by_id"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        order_id = next(tracker.get_latest_entity_values("order_id"), None)
        if not order_id: return [dispatcher.utter_message("Please provide a valid order ID.")]

        order = collection.find_one({"sm_orderid": order_id})
        if not order: return [dispatcher.utter_message(f"No order found with ID **{order_id}**.")]

        details = {
            "Order ID": order.get("sm_orderid", "N/A"),
            "Sender City": order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
            "Receiver Address": order.get("end", {}).get("address", {}).get("mapData", {}).get("address", "Unknown"),
            "Invoice Number": order.get("invoiceNo", "N/A"),
            "Payment Mode": order.get("paymentInfo", [{}])[0].get("paymentMode", "N/A"),
            "LR Number": order.get("lrNumber", "N/A")
        }
        
        message = "\n".join([f"- **{k}**: {v}" for k, v in details.items()])
        
        dispatcher.utter_message(
            text=f"**Order Details for {details['Order ID']}**:\n{message}",
            custom={"table_data": [details]}
        )
        return []

class ActionShowOrderTrends(Action):
    def name(self) -> Text:
        return "action_show_order_trends"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        customer_input = tracker.get_slot("customer_name")
        if not customer_input: return [dispatcher.utter_message("Please specify a customer name.")]

        message = tracker.latest_message.get("text", "").lower()
        match = re.search(r'(\d+)', message)
        duration = int(match.group()) if match else 30
        unit = "months" if "month" in message else "days"
        start_date = datetime.now() - timedelta(days=duration * 30 if unit == "months" else duration)

        query = {"start.contact.name": {"$regex": customer_input, "$options": "i"}, "createdAt": {"$gte": start_date}}
        matched_orders = list(collection.find(query))
        if not matched_orders: return [dispatcher.utter_message(f"No orders found for **{customer_input}** in this period.")]

        df = pd.DataFrame([o['createdAt'] for o in matched_orders], columns=["date"])
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        
        resample_key = 'M' if unit == 'months' else 'D'
        trend_data = df.resample(resample_key).size().reset_index(name='order_count')
        trend_data['date'] = trend_data['date'].dt.strftime('%Y-%m' if unit == 'months' else '%Y-%m-%d')

        plt.figure(figsize=(10, 5))
        plt.plot(trend_data["date"], trend_data["order_count"], marker='o', linestyle='-')
        plt.title(f"Order Trend for {customer_input} (Last {duration} {unit.title()})")
        plt.xlabel("Date"); plt.ylabel("Number of Orders")
        plt.xticks(rotation=45); plt.grid(True); plt.tight_layout()

        os.makedirs("static/graphs", exist_ok=True)
        safe_customer = re.sub(r'\W+', '_', customer_input)
        filename = f"trend_{safe_customer}_{duration}{unit}.png"
        filepath = os.path.join("static/graphs", filename)
        plt.savefig(filepath)
        plt.close()

        public_url = f"http://51.20.18.59:8080/static/graphs/{filename}"
        message = f"Here is the order trend graph for **{customer_input}** for the last {duration} {unit}."

        dispatcher.utter_message(text=message, image=public_url)
        return []

class ActionGetPendingOrdersByPickupCity(Action):
    def name(self) -> Text:
        return "action_get_pending_orders_by_pickup_city"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        pickup_city = extract_pickup_city(tracker.latest_message.get("text", ""))
        customer_input = tracker.get_slot("customer_name")

        if not pickup_city:
            dispatcher.utter_message("Please provide a pickup city to filter pending orders.")
            return []

        PENDING_STATUSES = [s for s in known_statuses if "delivered" not in s and "cancelled" not in s]
        
        query = {"orderStatus": {"$in": PENDING_STATUSES}, "start.address.mapData.city": {"$regex": f"^{pickup_city}$", "$options": "i"}}
        if customer_input: query["start.contact.name"] = {"$regex": customer_input, "$options": "i"}
        
        matched_orders = list(collection.find(query))
        
        msg_part = f"pending orders from **{pickup_city}**"
        if customer_input: msg_part += f" for **{customer_input}**"

        if not matched_orders: return [dispatcher.utter_message(f"No {msg_part}.")]

        now_utc = datetime.now(pytz.utc)
        rows = []
        for o in matched_orders:
            created_at_utc = o.get("createdAt")
            if created_at_utc and created_at_utc.tzinfo is None: created_at_utc = pytz.utc.localize(created_at_utc)
            
            rows.append({
                "Customer Name": o.get("start", {}).get("contact", {}).get("name", "Unknown"),
                "Order Booked Date": created_at_utc,
                "Pending For (Days)": (now_utc - created_at_utc).days if created_at_utc else "N/A",
                "Destination Location": o.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
                "Current Status": o.get("orderStatus", "unknown")
            })

        public_url = create_excel_file(rows, f"pending_{pickup_city}")
        dispatcher.utter_message(
            text=f"Found **{len(rows)}** {msg_part}.",
            custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
        )
        return []

class ActionGetCustomerPendingOrdersAllCities(Action):
    def name(self) -> Text:
        return "action_get_customer_pending_orders_all_cities"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if collection is None: return [dispatcher.utter_message("Database connection is not available.")]

        customer_input = tracker.get_slot("customer_name")
        if not customer_input: return [dispatcher.utter_message("Please provide a customer name (e.g., 'Ola') to fetch their pending orders.")]

        PENDING_STATUSES = [s for s in known_statuses if "delivered" not in s and "cancelled" not in s]
        if not PENDING_STATUSES: return [dispatcher.utter_message("Could not determine pending statuses.")]

        query = {"orderStatus": {"$in": PENDING_STATUSES}, "start.contact.name": {"$regex": customer_input, "$options": "i"}}
        
        try:
            matched_orders = list(collection.find(query))
            if not matched_orders: return [dispatcher.utter_message(f"No pending orders found for **{customer_input}** across all locations.")]

            now_utc = datetime.now(pytz.utc)
            rows, city_counts = [], defaultdict(int)

            for order in matched_orders:
                pickup_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
                city_counts[pickup_city] += 1
                
                created_at = order.get("createdAt")
                created_at_utc = pytz.utc.localize(created_at) if created_at and created_at.tzinfo is None else created_at

                rows.append({
                    "Pickup City": pickup_city, "Order ID": order.get("sm_orderid", "N/A"),
                    "Booking Date": created_at_utc,
                    "Pending For (Days)": (now_utc - created_at_utc).days if created_at_utc else "N/A",
                    "Destination City": order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
                    "Current Status": order.get("orderStatus", "unknown")
                })

            summary = ", ".join([f"{city}: {count}" for city, count in sorted(city_counts.items())])
            message = (f"Found a total of **{len(rows)}** pending orders for **{customer_input}**. "
                       f"Summary by location: {summary}")
            
            public_url = create_excel_file(rows, f"pending_orders_{customer_input}_by_location")
            dispatcher.utter_message(
                text=message,
                custom={"table_data": serialize_for_json(rows), "excel_url": public_url}
            )

        except Exception as e:
            print(f"Error in action_get_customer_pending_orders_all_cities: {e}")
            dispatcher.utter_message(f"An error occurred while retrieving orders: {str(e)}")
            
        return []

# Fallback for any unhandled intents
class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="I'm sorry, I didn't quite understand that. Can you please rephrase?")
        return []