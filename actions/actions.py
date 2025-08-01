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
from datetime import datetime
from datetime import datetime, timedelta
from collections import Counter
from bson.regex import Regex
from collections import defaultdict
import pytz

client = MongoClient("mongodb+srv://ordersDbReader:7HFtko7GNplIIi11@orders-flex-cluster.wbz5pht.mongodb.net/w=majority&appName=orders-flex-cluster")
db = client["orders-db"]
collection = db["SaaS_Orders"]

sender_cities = collection.distinct("start.address.mapData.city")
receiver_cities = collection.distinct("end.address.mapData.city")
known_cities = list(set(sender_cities + receiver_cities))
known_statuses = list(collection.distinct("orderStatus"))

pretty_status_labels = {
    "at_fm_agent_hub": "At First-Mile Hub",
    "at_lm_agent_hub": "At Last-Mile Hub",
    "fm_package_verified": "First-Mile Package Verified",
    "handed_over_to_agent": "Handed Over to Agent",
    "handed_over_to_midmile_shipper": "Handed to Mid-Mile Shipper",
    "lm_delayed": "Last-Mile Delay",
    "out_for_delivery": "Out for Delivery",
    "out_for_pickup": "Out for Pickup",
    "pickup_failed": "Pickup Failed",
    "delivered": "Delivered",
    "delivered_to_neighbour": "Delivered to Neighbour",
    "delivered_to_watchman": "Delivered to Watchman",
    "in_transit_to_destination_city": "In Transit to Destination"
}

def get_aesthetic_status(raw_status: str) -> str:
    return pretty_status_labels.get(raw_status, raw_status.replace("_", " ").title())


def fuzzy_city_match(city_name, known_cities, top_n=3, min_score=50):
    matches = process.extract(city_name, known_cities, scorer=fuzz.token_sort_ratio, limit=top_n)
    print(f"[DEBUG] Fuzzy city match for '{city_name}': {matches}")
    return matches[0][0] if matches and matches[0][1] >= min_score else None

def fuzzy_status_match(status_input, known_statuses=known_statuses, min_score=70):
    match = process.extractOne(status_input, known_statuses, scorer=fuzz.token_sort_ratio)
    print(f"[DEBUG] Fuzzy status match for '{status_input}': {match}")
    return match[0] if match and match[1] >= min_score else None

def extract_cities_by_keywords(text: str):
    pickup, drop = None, None
    text = text.lower()
    print(f"[DEBUG] Raw user text: {text}")
    if "from" in text and "to" in text:
        try:
            pickup_raw = text.split("from")[1].split("to")[0].strip()
            drop_raw = text.split("to")[1].strip()
            pickup = fuzzy_city_match(pickup_raw, known_cities)
            drop = fuzzy_city_match(drop_raw, known_cities)
        except Exception as e:
            print(f"[DEBUG] Error extracting cities: {e}")
    return pickup, drop

def extract_destination_city(text: str) -> Optional[str]:
    keywords = ["to", "delivered to", "reaching", "destination", "sent to", "shipped to", "towards", "arriving at"]
    text_lower = text.lower()
    print(f"[DEBUG] Text for destination extraction: {text_lower}")
    for kw in keywords:
        if kw in text_lower:
            try:
                city_part = text_lower.split(kw)[-1].strip()
                matched_city = fuzzy_city_match(city_part, known_cities)
                print(f"[DEBUG] Keyword: {kw}, City Part: {city_part}, Matched: {matched_city}")
                return matched_city
            except Exception as e:
                print(f"[DEBUG] Error in destination extraction for '{kw}': {e}")
                continue
    return None

from typing import Optional

def extract_pickup_city(text: str) -> Optional[str]:
    keywords = ["from", "pickup from", "collected from", "picked up at", "dispatched from", "shipping from", "leaving from"]
    text_lower = text.lower()
    print(f"[DEBUG] Text for pickup extraction: {text_lower}")

    for kw in keywords:
        if kw in text_lower:
            try:
                city_part = text_lower.split(kw)[-1].strip()
                matched_city = fuzzy_city_match(city_part, known_cities)
                print(f"[DEBUG] Keyword: {kw}, City Part: {city_part}, Matched: {matched_city}")
                return matched_city
            except Exception as e:
                print(f"[DEBUG] Error in pickup extraction for '{kw}': {e}")
                continue

    return None


def extract_dates_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    print(f"[DEBUG] Text for date extraction: {text}")
    text = text.lower().replace("–", "-").replace(" to ", " - ").replace(" and ", " - ").replace("between ", "")
    text = re.sub(r"[^\w\s\-/]", "", text)
    date_patterns = re.findall(r"(\d{1,4}[-/]\d{1,2}[-/]\d{1,4})", text)
    try:
        start_date = parser.parse(date_patterns[0]).date().isoformat()
        end_date = parser.parse(date_patterns[1]).date().isoformat()
        print(f"[DEBUG] Extracted dates: {start_date} to {end_date}")
        return start_date, end_date
    except Exception as e:
        print(f"[DEBUG] Date parsing failed: {e}")
        return None, None

def find_matching_customers(keyword: str) -> List[str]:
    print(f"[DEBUG] Finding customer names matching: {keyword}")
    names = collection.distinct("Sender Name")
    matched = [name for name in names if keyword.lower() in name.lower()]
    print(f"[DEBUG] Matched customers: {matched}")
    return matched

def extract_timestamp(raw_ts):
    try:
        if isinstance(raw_ts, dict):
            ts_val = raw_ts.get("$date")
            if isinstance(ts_val, dict) and "$numberLong" in ts_val:
                return datetime.fromtimestamp(int(ts_val["$numberLong"]) / 1000)
            elif isinstance(ts_val, int) or isinstance(ts_val, float):
                return datetime.fromtimestamp(ts_val / 1000)
        elif isinstance(raw_ts, datetime):
            return raw_ts
    except Exception:
        return None

def get_all_unique_shipper_uids():
    print("[DEBUG] Fetching all unique shipperUids from root and nested fields...")
    pipeline = [
        {
            "$project": {
                "root": "$shipperUid",
                "mid": "$midMile.shipperUid",
                "last": "$lastMile.shipperUid"
            }
        },
        {
            "$project": {
                "uids": {
                    "$setUnion": [
                        {"$cond": [{"$ne": ["$root", None]}, ["$root"], []]},
                        {"$cond": [{"$ne": ["$mid", None]}, ["$mid"], []]},
                        {"$cond": [{"$ne": ["$last", None]}, ["$last"], []]}
                    ]
                }
            }
        },
        {"$unwind": "$uids"},
        {"$group": {"_id": None, "all_uids": {"$addToSet": "$uids"}}}
    ]

    result = list(collection.aggregate(pipeline))
    all_uids = result[0]["all_uids"] if result else []
    print(f"[DEBUG] Unique shipperUids from DB: {all_uids}")
    return all_uids


def extract_location_code_from_text(user_text: str) -> Optional[str]:
    print(f"[DEBUG] Raw user text: {user_text}")

    
    cleaned_text = re.sub(r'[^a-zA-Z\s]', ' ', user_text)
    tokens = cleaned_text.lower().split()
    print(f"[DEBUG] Cleaned tokens: {tokens}")

    
    shipper_uids = get_all_unique_shipper_uids()

    if not shipper_uids:
        print("[DEBUG] No shipperUids found in DB.")
        return None

    
    best_match = None
    best_score = 0
    for token in tokens:
        result = process.extractOne(token, shipper_uids, scorer=fuzz.ratio)
        if result and result[1] > best_score:
            best_match, best_score = result[0], result[1]

    if best_score > 60:
        print(f"[DEBUG] Best fuzzy match: {best_match} (score: {best_score})")
        return best_match
    else:
        print(f"[DEBUG] No fuzzy match above threshold. Best score: {best_score}")
        return None

def serialize_for_json(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%d')
    if isinstance(obj, list):
        return [serialize_for_json(i) for i in obj]
    if isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    return obj

class ActionCxOrder(Action):
    def name(self) -> Text:
        return "action_cx_date"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        start_time = datetime.now()
        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "")
        s_date_str, e_date_str = extract_dates_from_text(message_text)

        try:
            s_date = parser.parse(s_date_str) if s_date_str else None
            e_date = parser.parse(e_date_str) if e_date_str else None
        except Exception:
            dispatcher.utter_message("Invalid date format. Please try again.")
            return []

        if s_date and e_date:
            e_date_plus = e_date + timedelta(days=1)
        else:
            dispatcher.utter_message("Start or end date missing.")
            return []

        if not customer_input:
            dispatcher.utter_message("Please provide a customer name.")
            return []

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]
        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        regex_conditions = [{"start.contact.name": {"$regex": name.strip(), "$options": "i"}} for name in matched_customers]

        query = {
            "$and": [
                {"$or": regex_conditions},
                {"createdAt": {"$gte": s_date, "$lt": e_date_plus}}
            ]
        }

        matched_orders = list(collection.find(query))
        if not matched_orders:
            dispatcher.utter_message("No orders found for the given customer in the provided date range.")
            return []

        message = f"Orders for **{customer_input}** from **{s_date.date()}** to **{e_date.date()}**:\n\n"
        message += f"{'Order ID':<40} {'From':<15} {'To':<15} {'Status':<30}\n"
        message += f"{'-'*40} {'-'*15} {'-'*15} {'-'*30}\n"

        rows = []
        for order in matched_orders:
            order_id = order.get("orderId", "N/A")
            from_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            raw_status = order.get("status", "unknown")
            aesthetic_status = get_aesthetic_status(raw_status)

            if len(rows) < 10:
                message += f"{order_id:<40} {from_city:<15} {to_city:<15} {aesthetic_status:<30}\n"

            rows.append({
                "Order ID": order_id,
                "Customer": order.get("start", {}).get("contact", {}).get("name", "Unknown"),
                "From City": from_city,
                "To City": to_city,
                "Status": aesthetic_status,
                "Created At": order.get("createdAt")
            })

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = "customer_orders_by_date.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_cx_date took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []


class ActionrouteOrder(Action):
    def name(self) -> Text:
        return "action_route"

    def run(self, dispatcher, tracker, domain):
        start_time = datetime.now()
        message_text = tracker.latest_message.get("text", "")
        pickup, drop = extract_cities_by_keywords(message_text)

        if not pickup or not drop:
            dispatcher.utter_message("Please provide both pickup and drop locations.")
            return []

        matched_orders = list(collection.find({
            "start.address.mapData.city": {"$regex": f"^{pickup}$", "$options": "i"},
            "end.address.mapData.city": {"$regex": f"^{drop}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found from {pickup} to {drop}.")
            return []

        message = f" Orders from {pickup} to {drop}:\n\n"
        message += f"{'Order ID':<40} {'Sender':<20} {'Booking Date':<15}\n"
        message += f"{'-'*40} {'-'*20} {'-'*15}\n"
        rows = []

        for order in matched_orders[:10]:
            order_id = order.get("orderId", "N/A")
            sender = order.get("start", {}).get("contact", {}).get("name", "Unknown")
            created_at = order.get("createdAt")
            created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else str(created_at)
            message += f"{order_id:<40} {sender:<20} {created_date:<15}\n"

        for order in matched_orders:
            rows.append({
                "Order ID": order.get("orderId", "N/A"),
                "Sender": order.get("start", {}).get("contact", {}).get("name", "Unknown"),
                "Pickup City": pickup,
                "Drop City": drop,
                "Created At": order.get("createdAt")
            })

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = "orders_by_route.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_route took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []

class ActionFordestination(Action):
    def name(self) -> Text:
        return "action_cx_destination"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        start_time = datetime.now()
        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "")
        destination = extract_destination_city(message_text)

        if not customer_input or not destination:
            dispatcher.utter_message("Please provide both customer name and destination.")
            return []

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]
        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        matched_orders = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "end.address.mapData.city": {"$regex": f"^{destination}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message("No orders found for the given customer to that destination.")
            return []

        message = f" Orders for **{customer_input}** delivered to **{destination}**:\n\n"
        message += f"{'Order ID':<40} {'From':<20} {'To':<20}\n"
        message += f"{'-'*40} {'-'*20} {'-'*20}\n"
        rows = []

        for order in matched_orders[:10]:
            order_id = order.get("orderId", "N/A")
            from_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            message += f"{order_id:<40} {from_city:<20} {to_city:<20}\n"

        for order in matched_orders:
            rows.append({
                "Order ID": order.get("orderId", "N/A"),
                "Customer": order.get("start", {}).get("contact", {}).get("name", "Unknown"),
                "From City": order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
                "To City": order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown"),
                "Created At": order.get("createdAt")
            })

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = "customer_orders_by_destination.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_cx_destination took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []

class ActionGetOrdersByStatus(Action):
    def name(self) -> Text:
        return "action_get_orders_by_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()
        message_text = tracker.latest_message.get("text", "").lower()
        customer_input = tracker.get_slot("customer_name")

        status_mapping = {
            "pending": [
                "at_fm_agent_hub", "at_lm_agent_hub", "fm_package_verified",
                "handed_over_to_agent", "handed_over_to_midmile_shipper",
                "lm_delayed", "out_for_delivery", "out_for_pickup", "pickup_failed"
            ],
            "delivered": ["delivered", "delivered_to_neighbour", "delivered_to_watchman"],
            "in transit": ["in_transit_to_destination_city"]
        }
        status_aliases = {
            "LMD": "lm_delayed",
            "last mile delay": "lm_delayed",
            "last-mile delay": "lm_delayed",

            "FMD": "fm_package_verified",
            "first mile delay": "fm_package_verified",
            "package verification": "fm_package_verified",

            "AFMH": "at_fm_agent_hub",
            "at first mile hub": "at_fm_agent_hub",

            "ALMH": "at_lm_agent_hub",
            "at last mile hub": "at_lm_agent_hub",

            "PF": "pickup_failed",
            "pickup failed": "pickup_failed",

            "OFD": "out_for_delivery",
            "out for delivery": "out_for_delivery",

            "OFP": "out_for_pickup",
            "out for pickup": "out_for_pickup",

            "HOA": "handed_over_to_agent",
            "handover to agent": "handed_over_to_agent",

            "HOS": "handed_over_to_midmile_shipper",
            "handover to shipper": "handed_over_to_midmile_shipper",

            "IT": "in_transit_to_destination_city",
            "in transit": "in_transit_to_destination_city",

            "DEL": "delivered",
            "delivered": "delivered",

            "DELN": "delivered_to_neighbour",
            "delivered to neighbour": "delivered_to_neighbour",

            "DELW": "delivered_to_watchman",
            "delivered to watchman": "delivered_to_watchman"
        }

  

        custom_filter = {}
        specific_status = None

        for phrase, raw_status in status_aliases.items():
            if phrase in message_text:
                specific_status = raw_status
                break
        else:
            for raw_status, pretty in pretty_status_labels.items():
                if raw_status in message_text or pretty.lower() in message_text:
                    specific_status = raw_status
                    break

        if specific_status:
            custom_filter["orderStatus"] = specific_status
        else:
            status_category = None
            if any(word in message_text for word in ["delivered"]):
                status_category = "delivered"
            elif any(word in message_text for word in ["cancelled", "canceled", "pending", "waiting", "pickup", "delayed"]):
                status_category = "pending"
            elif any(word in message_text for word in ["in transit", "transit", "shipped", "on the way"]):
                status_category = "in transit"

            if status_category:
                custom_filter["orderStatus"] = {"$in": status_mapping[status_category]}
            else:
                status = fuzzy_status_match(message_text)
                if not status:
                    dispatcher.utter_message("Sorry, I couldn't identify the delivery status you're looking for.")
                    return []
                custom_filter["orderStatus"] = {"$regex": f"^{status}$", "$options": "i"}

        if customer_input:
            all_names = collection.distinct("start.contact.name")
            matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]
            if not matched_customers:
                dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
                return []

            regex_conditions = [{"start.contact.name": {"$regex": name.strip(), "$options": "i"}} for name in matched_customers]
            custom_filter["$or"] = regex_conditions

        matched_orders = list(collection.find(custom_filter))

        if not matched_orders:
            dispatcher.utter_message("No orders found for the requested filters.")
            return []

        customer_name = customer_input or "Unknown Customer"
        message = f"**Orders for {customer_name}**\n\n"
        message += f"{'Order ID':<35} {'Customer':<25} {'Status':<30} {'Date':<12}\n"
        message += f"{'-'*35} {'-'*25} {'-'*30} {'-'*12}\n"

        rows = []

        for order in matched_orders[:10]:
            order_id = order.get("orderId", "N/A")
            customer = order.get("start", {}).get("contact", {}).get("name", "Unknown")
            raw_status = order.get("orderStatus", order.get("Order Status", "Unknown"))
            status = get_aesthetic_status(raw_status)
            created_at = order.get("createdAt", None)
            booking_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, 'strftime') else str(created_at)

            message += f"{order_id:<35} {customer:<25} {status:<30} {booking_date:<12}\n"
            rows.append({
                "Order ID": order_id,
                "Customer": customer,
                "Status": status,
                "Date": booking_date
            })

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = "orders_by_status.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)
        public_url = f"http://16.171.255.49:3000/static/files/{filename}"

        dispatcher.utter_message(custom={
            "table_data": serialize_for_json(rows[:10]),
            "excel_url": public_url
        })

        print(f"[TIME] action_get_orders_by_status took {time.time() - start_time:.2f} seconds")
        return []



class ActionGetOrderStatus(Action):
    def name(self) -> Text:
        return "action_get_order_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()

        order_id = next(tracker.get_latest_entity_values("order_id"), None)

        if not order_id:
            dispatcher.utter_message("Please provide the order ID to check its status.")
            print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
            return []

        order = collection.find_one({
            "$or": [
                {"orderId": order_id},
                {"Order ID": order_id}
            ]
        })

        if not order:
            dispatcher.utter_message(f"No order found with ID {order_id}.")
            print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
            return []

        raw_status = order.get("orderStatus") or order.get("Order Status") or "Unknown"
        aesthetic_status = get_aesthetic_status(raw_status)

        message = f"Status of order ID {order_id}: {aesthetic_status}"

        delivery_date = None
        if raw_status.lower() == "delivered":
            delivery_event = next(
                (event for event in order.get("orderStatusEvents", [])
                 if event.get("status", "").lower() == "delivered"),
                None
            )
            if delivery_event:
                timestamp = delivery_event.get("timeStamp", {})
                try:
                    ts = int(timestamp.get("$date", {}).get("$numberLong", 0))
                    delivery_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                    message += f". It was delivered on {delivery_date}."
                except Exception:
                    message += ". Delivery date format is invalid."
            else:
                message += ". Delivery date not available."

        dispatcher.utter_message(message)

        custom_data = {
            "Order ID": order_id,
            "Status": aesthetic_status
        }
        if delivery_date:
            custom_data["Delivery Date"] = delivery_date

        dispatcher.utter_message(custom={"order_status": custom_data})

        print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
        return []

class ActionGetOrdersByTAT(Action):
    def name(self) -> Text:
        return "action_get_orders_by_tat"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()
        message_text = tracker.latest_message.get("text", "").lower()
        match = re.search(r"\b(\d+)\s*(day|days)?\b", message_text)

        if not match:
            dispatcher.utter_message("Please specify the number of days to match TAT.")
            print(f"[TIME] action_get_orders_by_tat took {time.time() - start_time:.2f} seconds")
            return []

        try:
            tat_days = int(match.group(1))
        except ValueError:
            dispatcher.utter_message("Invalid number of days provided.")
            print(f"[TIME] action_get_orders_by_tat took {time.time() - start_time:.2f} seconds")
            return []

        delivered_orders = list(collection.find({
            "orderStatus": {"$regex": "^delivered$", "$options": "i"}
        }))
        total_delivered = len(delivered_orders)
        matching_orders = []

        for order in delivered_orders:
            paid_at_raw = order.get("paymentInfo", [{}])[0].get("paidAt")
            booking_ts = extract_timestamp(paid_at_raw)

            delivery_ts = None
            for mutation in order.get("mutations", []):
                if mutation.get("eventType") == "order_delivered":
                    delivery_ts_raw = mutation.get("eventTimeStamp")
                    delivery_ts = extract_timestamp(delivery_ts_raw)
                    break

            if booking_ts and delivery_ts:
                tat = (delivery_ts - booking_ts).days
                if tat == tat_days:
                    matching_orders.append({
                        "Order ID": order.get("orderId", "N/A"),
                        "Sender": order.get("start", {}).get("contact", {}).get("name", "Unknown"),
                        "Booking Date": booking_ts.strftime('%Y-%m-%d'),
                        "Delivery Date": delivery_ts.strftime('%Y-%m-%d'),
                        "TAT (days)": tat
                    })

        message = (
            f"Total delivered orders in DB: {total_delivered}\n"
            f"Delivered in {tat_days} days: {len(matching_orders)}\n\n"
        )
        message += f"{'Order ID':<35} {'Sender':<25} {'Booking Date':<15} {'Delivery Date':<15} {'TAT':<5}\n"
        message += f"{'-'*35} {'-'*25} {'-'*15} {'-'*15} {'-'*5}\n"

        for o in matching_orders[:10]:
            message += f"{o['Order ID']:<35} {o['Sender']:<25} {o['Booking Date']:<15} {o['Delivery Date']:<15} {o['TAT (days)']:<5}\n"

        if not matching_orders:
            message += "No orders found matching the given TAT."

        dispatcher.utter_message(message)

        if matching_orders:
            df = pd.DataFrame(matching_orders)
            os.makedirs("static/files", exist_ok=True)
            filename = f"orders_by_tat_{tat_days}d.xlsx"
            filepath = os.path.join("static/files", filename)
            df.to_excel(filepath, index=False)

            public_url = f"http://16.171.255.49:3000/static/files/{filename}"
            dispatcher.utter_message(custom={"table_data": serialize_for_json(matching_orders), "excel_url": public_url})

        print(f"[TIME] action_get_orders_by_tat took {time.time() - start_time:.2f} seconds")
        return []
    
class ActionPendingOrdersPastDays(Action):
    def name(self) -> Text:
        return "action_pending_orders_past_days"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = datetime.now()
        message_text = tracker.latest_message.get("text", "").lower()
        customer_input = tracker.get_slot("customer_name") or ""

        delivered_statuses = [
            "delivered",
            "delivered_at_security",
            "delivered_at_neighbor",
            "cancelled"
        ]

        match = re.search(r"(\d+)\s*days?", message_text)
        if not match:
            dispatcher.utter_message("Please specify how many past days to consider.")
            return []

        try:
            n_days = int(match.group(1))
        except ValueError:
            dispatcher.utter_message("Couldn't interpret the number of days.")
            return []

        date_cutoff = datetime.now() - timedelta(days=n_days)

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        results = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "orderStatus": {"$nin": delivered_statuses},
            "createdAt": {"$gte": date_cutoff}
        }))

        if not results:
            dispatcher.utter_message(f"No pending orders found for '{customer_input}' in the past {n_days} days.")
            return []

        rows = []
        message = f"Pending orders for **{customer_input}** in the past **{n_days}** days:\n"
        message += f"{'Order ID':<35} {'Status':<35} {'To City':<20} {'Created At':<15}\n"
        message += f"{'-'*35} {'-'*35} {'-'*20} {'-'*15}\n"

        for order in results[:10]:
            order_id = order.get("orderId", "N/A")
            raw_status = order.get("orderStatus", "unknown")
            status = get_aesthetic_status(raw_status)
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            created_at = order.get("createdAt")
            created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, "strftime") else str(created_at)

            message += f"{order_id:<35} {status:<35} {to_city:<20} {created_date:<15}\n"

        for order in results:
            order_id = order.get("orderId", "N/A")
            raw_status = order.get("orderStatus", "unknown")
            status = get_aesthetic_status(raw_status)
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            created_at = order.get("createdAt")
            created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, "strftime") else str(created_at)

            rows.append({
                "Order ID": order_id,
                "Status": status,
                "To City": to_city,
                "Created At": created_date
            })

        message += f"\nTotal pending orders: {len(results)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)

        safe_customer_name = re.sub(r'\W+', '_', customer_input).strip('_') or "customer"
        filename = f"pending_orders_{safe_customer_name}_{n_days}days.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_pending_orders_past_days took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []

class ActionTopPincodesByCustomer(Action):
    def name(self) -> Text:
        return "action_top_pincodes_by_customer"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()
        customer_input = tracker.get_slot("customer_name")

        if not customer_input:
            dispatcher.utter_message("Please provide a customer name.")
            return []

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        orders = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "end.address.mapData.pincode": {"$exists": True, "$ne": ""}
        }))

        if not orders:
            dispatcher.utter_message(f"No orders found for customers matching '{customer_input}'.")
            return []

        pincode_counter = Counter()
        for order in orders:
            pincode = order.get("end", {}).get("address", {}).get("mapData", {}).get("pincode")
            if pincode:
                pincode_counter[pincode] += 1

        top_pincodes = pincode_counter.most_common(10)

        if not top_pincodes:
            dispatcher.utter_message("No destination pincodes found.")
            return []

        message = f"Top 10 delivery pincodes for customers matching '{customer_input}':\n"
        message += f"Matched names: {', '.join(matched_customers)}\n\n"
        message += f"{'S.No.':<6} {'Pincode':<12} {'Order Count':<12}\n"
        message += f"{'-'*6} {'-'*12} {'-'*12}\n"

        rows = []
        for i, (pincode, count) in enumerate(top_pincodes, start=1):
            message += f"{i:<6} {pincode:<12} {count:<12}\n"
            rows.append({"Pincode": pincode, "Order Count": count})

        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = f"top_pincodes_{customer_input.replace(' ', '_')}.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            pincodes_json = []
            for i, (pincode, count) in enumerate(top_pincodes, start=1):
                pincodes_json.append({
                    "Pincode": pincode,
                    "Order Count": count
                })
            dispatcher.utter_message(custom={"table_data": serialize_for_json(pincodes_json), "excel_url": public_url})

        print(f"[TIME] action_top_pincodes_by_customer took {(time.time() - start_time):.2f} seconds")
        return []

class ActionDynamicOrderQuery(Action):
    def name(self) -> Text:
        return "action_dynamic_order_query"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        import time
        from datetime import datetime, timedelta

        start_time = time.time()
        user_text = tracker.latest_message.get("text", "").lower()

        delivery_keywords = [
            "delivered", "delivery report", "delivery summary", "delivered shipments",
            "orders delivered", "shipment summary", "delivered report", "completed orders"
        ]

        location_code = extract_location_code_from_text(user_text)
        start_date_str, end_date_str = extract_dates_from_text(user_text)

        try:
            start_dt = parser.parse(start_date_str) if start_date_str else None
            end_dt = parser.parse(end_date_str) + timedelta(days=1) if end_date_str else None
        except:
            dispatcher.utter_message("Invalid date format. Please try again.")
            return []

        is_delivery_report = any(kw in user_text for kw in delivery_keywords)
        is_location_query = bool(location_code)

        if (not is_location_query and is_delivery_report) or (not is_location_query and start_dt and end_dt):
            is_delivery_report = True

        rows = []
        filename = ""
        message = ""

        if is_delivery_report and start_dt and end_dt:
            query = {
                "orderStatus": {"$in": ["delivered", "delivered_at_security", "delivered_at_neighbor"]},
                "createdAt": {"$gte": start_dt, "$lt": end_dt}
            }
            results = list(collection.find(query))

            if not results:
                dispatcher.utter_message(f"No delivered orders found between **{start_date_str}** and **{end_date_str}**.")
                return []

            message = f"**Delivered Orders between {start_date_str} and {end_date_str}:**\n"
            message += f"{'Order ID':<24} {'Status':<35} {'Created At':<12}\n"
            message += f"{'-'*24} {'-'*35} {'-'*12}\n"

            for order in results:
                order_id = order.get("orderId", "N/A")
                raw_status = order.get("orderStatus", "delivered")
                status = get_aesthetic_status(raw_status)
                created = order.get("createdAt")
                created_str = created.strftime('%Y-%m-%d') if hasattr(created, 'strftime') else str(created)

                rows.append({
                    "Order ID": order_id,
                    "Status": status,
                    "Created At": created_str
                })

            for row in rows[:10]:
                message += f"{row['Order ID']:<24} {row['Status']:<35} {row['Created At']:<12}\n"

            filename = f"delivered_orders_{start_date_str}_to_{end_date_str}.xlsx"

        elif is_location_query and start_dt and end_dt:
            query = {
                "$and": [
                    {
                        "$or": [
                            {"firstMile.shipperUid": {"$regex": f"^{location_code}$", "$options": "i"}},
                            {"midMile.shipperUid": {"$regex": f"^{location_code}$", "$options": "i"}},
                            {"lastMile.shipperUid": {"$regex": f"^{location_code}$", "$options": "i"}},
                        ]
                    },
                    {"createdAt": {"$gte": start_dt, "$lt": end_dt}}
                ]
            }
            results = list(collection.find(query))

            if not results:
                dispatcher.utter_message(
                    f"No orders found for location ID **{location_code}** between **{start_date_str}** and **{end_date_str}**."
                )
                return []

            message = f"**Orders from location `{location_code}` between {start_date_str} and {end_date_str}:**\n"
            message += f"{'Order ID':<24} {'Status':<35} {'Created At':<12}\n"
            message += f"{'-'*24} {'-'*35} {'-'*12}\n"

            for order in results:
                order_id = order.get("orderId", "N/A")
                raw_status = order.get("orderStatus", "unknown")
                status = get_aesthetic_status(raw_status)
                created = order.get("createdAt")
                created_str = created.strftime('%Y-%m-%d') if hasattr(created, 'strftime') else str(created)

                rows.append({
                    "Order ID": order_id,
                    "Status": status,
                    "Created At": created_str
                })

            for row in rows[:10]:
                message += f"{row['Order ID']:<24} {row['Status']:<35} {row['Created At']:<12}\n"

            filename = f"orders_{location_code}_{start_date_str}_to_{end_date_str}.xlsx"

        else:
            dispatcher.utter_message("Please provide either a location ID or ask for a delivery report with valid dates.")
            return []

        message += f"\n**Total Records**: {len(rows)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = filename.replace(" ", "_").replace(":", "-")
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_dynamic_order_query took {(time.time() - start_time):.2f} seconds")
        return []


class ActionOrderStatusByInvoice(Action):
    def name(self) -> Text:
        return "action_order_status_by_invoice"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()
        invoice_number = next(tracker.get_latest_entity_values("invoice_number"), None)

        if not invoice_number:
            dispatcher.utter_message("Please provide a valid invoice number to check the order status.")
            print(f"[TIME] action_order_status_by_invoice took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "$or": [
                {"Invoice Number": {"$regex": f"^{invoice_number}$", "$options": "i"}},
                {"invoiceNo": {"$regex": f"^{invoice_number}$", "$options": "i"}}
            ]
        }))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found with invoice number {invoice_number}.")
            print(f"[TIME] action_order_status_by_invoice took {time.time() - start_time:.2f} seconds")
            return []

        rows = []
        message = f"Order(s) with invoice number **{invoice_number}**:\n"

        for order in matched_orders[::10]:
            order_id = order.get("sm_orderid") or order.get("Order ID", "N/A")
            raw_status = order.get("orderStatus") or order.get("Order Status", "Unknown")
            aesthetic_status = get_aesthetic_status(raw_status)
            created = order.get("createdAt")
            booking_date = created.strftime('%Y-%m-%d') if hasattr(created, 'strftime') else str(created)
            customer_name = order.get("start", {}).get("contact", {}).get("name", "Unknown")

            message += f"- **Order ID**: {order_id} | **Status**: {aesthetic_status} | **Date**: {booking_date} | **Customer**: {customer_name}\n"

            rows.append({
                "Order ID": order_id,
                "Invoice Number": invoice_number,
                "Status": aesthetic_status,
                "Customer": customer_name,
                "Booking Date": booking_date
            })

        message += f"\n**Total orders found**: {len(rows)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = f"order_status_invoice_{invoice_number}.xlsx".replace(" ", "_").replace(":", "-")
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if rows:
            dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_order_status_by_invoice took {(time.time() - start_time):.2f} seconds")
        return []


class ActionCheckServiceByPincode(Action):
    def name(self) -> Text:
        return "action_check_service_by_pincode"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()

        pincode = next(tracker.get_latest_entity_values("pincode"), None)

        if not pincode:
            dispatcher.utter_message("Please provide a valid pincode to check service availability.")
            print(f"[TIME] action_check_service_by_pincode took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "end.address.mapData.pincode": {"$regex": f"^{pincode}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message(f"Sorry, we currently do **not** provide service in pincode **{pincode}**.")
            print(f"[TIME] action_check_service_by_pincode took {time.time() - start_time:.2f} seconds")
            return []

        
        agent_names = set()
        for order in matched_orders:
            agent = order.get("deliveryAgent", {}).get("assignedTo")
            if agent:
                agent_names.add(agent)

        if agent_names:
            agent_list = ', '.join(agent_names)
            dispatcher.utter_message(f"Service is **available** in pincode **{pincode}**.\n Assigned delivery agent(s): **{agent_list}**.")
            dispatcher.utter_message(custom={"service": {"pincode": pincode, "agents": list(agent_names)}})
        else:
            dispatcher.utter_message(f"Service is **available** in pincode **{pincode}**, but no delivery agent has been assigned yet.")
            dispatcher.utter_message(custom={"service": {"pincode": pincode, "agents": []}})

        print(f"[TIME] action_check_service_by_pincode took {time.time() - start_time:.2f} seconds")
        return []

    
class ActionPendingOrdersBeforeLastTwoDays(Action):
    def name(self) -> Text:
        return "action_pending_orders_before_last_two_days"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = datetime.now()

        delivered_statuses = [
            "delivered", "delivered_at_security", "delivered_at_neighbor", "cancelled"
        ]
        cutoff_date = datetime.now() - timedelta(days=2)

        results = list(collection.find({
            "orderStatus": {"$nin": delivered_statuses},
            "createdAt": {"$lt": cutoff_date}
        }))

        if not results:
            dispatcher.utter_message("No pending orders found before the last 2 days.")
            return []

        rows = []
        message = f"**Pending orders created before {cutoff_date.strftime('%Y-%m-%d')}**\n"
        message += f"{'Order ID':<24} {'Customer':<20} {'Status':<30} {'To City':<15} {'Created At':<12}\n"
        message += f"{'-'*24} {'-'*20} {'-'*30} {'-'*15} {'-'*12}\n"

        for order in results:
            order_id = order.get("orderId", "N/A")
            raw_status = order.get("orderStatus", "Unknown")
            pretty_status = get_aesthetic_status(raw_status)
            created_at = order.get("createdAt")
            created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, "strftime") else str(created_at)
            customer_name = order.get("start", {}).get("contact", {}).get("name", "Unknown")
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")

            rows.append({
                "Order ID": order_id,
                "Customer": customer_name,
                "Status": pretty_status,
                "To City": to_city,
                "Created At": created_date
            })

        for row in rows[:10]:
            message += f"{row['Order ID']:<24} {row['Customer']:<20} {row['Status']:<30} {row['To City']:<15} {row['Created At']:<12}\n"

        message += f"\n**Total pending orders:** {len(rows)}"
        dispatcher.utter_message(message)

        df = pd.DataFrame(rows)
        os.makedirs("static/files", exist_ok=True)
        filename = "pending_orders_before_2days_all.xlsx"
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        dispatcher.utter_message(custom={"table_data": serialize_for_json(rows), "excel_url": public_url})

        print(f"[TIME] action_pending_orders_before_last_two_days took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []


class ActionOrderDetailsByID(Action):
    def name(self) -> Text:
        return "action_fetch_order_info_by_id"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()

        order_id = next(tracker.get_latest_entity_values("order_id"), None)

        
        if not order_id:
            dispatcher.utter_message("Please provide a valid order ID.")
            print(f"[TIME] action_fetch_order_info_by_id took {time.time() - start_time:.2f} seconds")
            return []

        
        order = collection.find_one({
            "$or": [{"orderId": order_id}, {"Order ID": order_id}]
        })

        
        if not order:
            dispatcher.utter_message(f"No order found with ID **{order_id}**.")
            print(f"[TIME] action_fetch_order_info_by_id took {time.time() - start_time:.2f} seconds")
            return []

        
        sender_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
        receiver_address = order.get("end", {}).get("address", {}).get("mapData", {}).get("address", "Unknown")
        invoice_number = order.get("invoiceNumber", order.get("Invoice Number", "N/A"))
        payment_mode = order.get("paymentInfo", [{}])[0].get("paymentMode", "N/A")
        lr_number = order.get("LR Number", order.get("lrNumber", "N/A"))

        
        message = (
            f"**Order Details for {order_id}**:\n"
            f"- Sender City: {sender_city}\n"
            f"- Receiver Address: {receiver_address}\n"
            f"- Invoice Number: {invoice_number}\n"
            f"- Payment Mode: {payment_mode}\n"
            f"-  LR Number: {lr_number}"
        )
        dispatcher.utter_message(message)

        
        df = pd.DataFrame([{
            "Order ID": order_id,
            "Sender City": sender_city,
            "Receiver Address": receiver_address,
            "Invoice Number": invoice_number,
            "Payment Mode": payment_mode,
            "LR Number": lr_number
        }])

        os.makedirs("static/files", exist_ok=True)
        filename = f"order_details_{order_id}.xlsx".replace(" ", "_").replace(":", "-")
        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        
        dispatcher.utter_message(custom={"table_data": serialize_for_json([{ 
                "Order ID": order_id,
                "Sender City": sender_city,
                "Receiver Address": receiver_address,
                "Invoice Number": invoice_number,
                "Payment Mode": payment_mode,
                "LR Number": lr_number
            }]), "excel_url": public_url})
        print(f"[TIME] action_fetch_order_info_by_id took {(time.time() - start_time):.2f} seconds")
        return []


class ActionCitywiseDeliveredOrderDistribution(Action):
    def name(self) -> Text:
        return "action_citywise_delivered_order_distribution"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        import pandas as pd
        from collections import Counter
        from bson.regex import Regex
        import os

        start_time = time.time()

        
        customer_name = next(tracker.get_latest_entity_values("customer_name"), None)

    
        query_filter = {
            "orderStatus": {"$in": ["delivered", "delivered_at_security", "delivered_at_neighbor"]}
        }

        if customer_name:
            query_filter["start.contact.name"] = Regex(customer_name, "i")

        results = list(collection.find(query_filter))

        if not results:
            msg = f"No delivered orders found"
            if customer_name:
                msg += f" for customer **{customer_name}**."
            else:
                msg += "."
            dispatcher.utter_message(msg)
            return []


        city_counts = Counter()
        filtered_orders = []

        for order in results[:10]:
            city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            order_id = order.get("orderId", "N/A")
            status = order.get("orderStatus", "delivered")
            customer = order.get("start", {}).get("contact", {}).get("name", "Unknown")
            city_counts[city] += 1
            filtered_orders.append({
                "Order ID": order_id,
                "City": city,
                "Customer": customer,
                "Status": status
            })

        sorted_city_data = sorted(city_counts.items(), key=lambda x: x[1], reverse=True)

        
        message = f" **Delivered Orders Distribution by City**"

        if customer_name:
            message += f" for customer **{customer_name}**\n"
        else:
            message += ":\n"

        message += f"\n{'City':<20} {'Order Count':<12}\n"
        message += f"{'-'*20} {'-'*12}\n"

        for city, count in sorted_city_data:
            message += f"{city:<20} {count:<12}\n"

        message += f"\n**Total Delivered Orders:** {len(results)}"

        dispatcher.utter_message(message)

        
        df = pd.DataFrame(filtered_orders)
        os.makedirs("static/files", exist_ok=True)
        filename = f"citywise_delivered_orders"
        if customer_name:
            filename += f"_{customer_name.replace(' ', '_')}"
        filename += ".xlsx"

        filepath = os.path.join("static/files", filename)
        df.to_excel(filepath, index=False)

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        if filtered_orders:
            filtered_orders_json = []
            for order in filtered_orders:
                filtered_orders_json.append({
                    "Order ID": order.get("Order ID"),
                    "City": order.get("City"),
                    "Customer": order.get("Customer"),
                    "Status": order.get("Status")
                })
            dispatcher.utter_message(custom={"table_data": serialize_for_json(filtered_orders_json), "excel_url": public_url})

        print(f"[TIME] action_citywise_delivered_order_distribution took {(time.time() - start_time):.2f} seconds")
        return []

class ActionShowOrderTrends(Action):
    def name(self) -> Text:
        return "action_show_order_trends"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:


        start_time = time.time()

        customer_input = tracker.get_slot("customer_name")
        if not customer_input:
            dispatcher.utter_message("Please tell me who you are (e.g., from Ola or Wakefit).")
            return []

        message = tracker.latest_message.get("text", "").lower()
        print(f"[DEBUG] Message: {message}")

        number_match = re.search(r'\d+', message)
        duration = int(number_match.group()) if number_match else 30

        unit = "days"
        if "month" in message:
            unit = "months"

        if unit == "months":
            start_date = datetime.now() - timedelta(days=duration * 30)
            group_by = 'M'
        else:
            start_date = datetime.now() - timedelta(days=duration)
            group_by = 'D'

        end_date = datetime.now()

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]
        if not matched_customers:
            dispatcher.utter_message(f"No matching customer found for '{customer_input}'.")
            return []

        regex_conditions = [{"start.contact.name": {"$regex": name, "$options": "i"}} for name in matched_customers]
        query = {
            "$and": [
                {"$or": regex_conditions},
                {"createdAt": {"$gte": start_date, "$lt": end_date}}
            ]
        }

        matched_orders = list(collection.find(query))
        if not matched_orders:
            dispatcher.utter_message("No orders found in the given range.")
            return []

        dates = [order["createdAt"].date() for order in matched_orders if "createdAt" in order]
        df = pd.DataFrame(dates, columns=["date"])
        df["date"] = pd.to_datetime(df["date"])
        df_grouped = df.groupby(df["date"].dt.to_period(group_by)).size().reset_index(name="order_count")
        df_grouped["date"] = df_grouped["date"].astype(str)

        plt.figure(figsize=(8, 4))
        plt.plot(df_grouped["date"], df_grouped["order_count"], marker='o')
        plt.title(f"{unit.title()}ly Order Trend for {customer_input.title()}")
        plt.xlabel("Month" if unit == "months" else "Date")
        plt.ylabel("Orders")
        plt.xticks(rotation=45)
        plt.tight_layout()

        os.makedirs("static/graphs", exist_ok=True)
        filename = f"trend_graph_{customer_input.replace(' ', '_')}_{unit}_{duration}.png"
        image_path = os.path.join("static/graphs", filename)
        plt.savefig(image_path)
        plt.close()

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        dispatcher.utter_message(f" Here is your order trend graph for the last {duration} {unit}:")
        dispatcher.utter_message(image=public_url)
        dispatcher.utter_message(f" [Click here to view the graph]({public_url})")
        dispatcher.utter_message(custom={"graph_url": public_url})
        print(f"[TIME] action_show_order_trends took {time.time() - start_time:.2f} seconds")
        return []

class ActionDelayedOrdersGraph(Action):
    def name(self) -> Text:
        return "action_delayed_orders_graph"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:


        start_time = time.time()

        customer_name = next(tracker.get_latest_entity_values("customer_name"), None)
        status_entity = next(tracker.get_latest_entity_values("order_status"), None)
        message = tracker.latest_message.get("text", "").lower()
        print(f"[DEBUG] Message: {message}")

        number_match = re.search(r'\d+', message)
        duration = int(number_match.group()) if number_match else 30
        unit = "days"
        if "month" in message:
            unit = "months"

        delivered_statuses = ["delivered", "delivered_at_security", "delivered_at_neighbor"]
        cancelled_statuses = ["cancelled", "canceled"]
        known_statuses = collection.distinct("orderStatus")

        if status_entity:
            if "deliver" in status_entity:
                filtered_statuses = delivered_statuses
                display_status = "Delivered"
            elif "cancel" in status_entity:
                filtered_statuses = cancelled_statuses
                display_status = "Cancelled"
            elif "delay" in status_entity or "pending" in status_entity:
                filtered_statuses = [s for s in known_statuses if s not in delivered_statuses + cancelled_statuses]
                display_status = "Pending"
            else:
                filtered_statuses = [status_entity]
                display_status = status_entity.capitalize()
        else:
            filtered_statuses = [s for s in known_statuses if s not in delivered_statuses + cancelled_statuses]
            display_status = "Pending"

        start_date = datetime.now() - timedelta(days=duration * 30 if unit == "months" else duration)

        query_filter = {
            "orderStatus": {"$in": filtered_statuses},
            "createdAt": {"$gte": start_date}
        }

        if customer_name:
            query_filter["start.contact.name"] = Regex(customer_name, "i")

        results = list(collection.find(query_filter))

        if not results:
            msg = f"No **{display_status}** orders found"
            if customer_name:
                msg += f" for **{customer_name}**"
            msg += f" in the last {duration} {unit}."
            dispatcher.utter_message(msg)
            return []

        dates = [order["createdAt"].date() for order in results if "createdAt" in order]
        df = pd.DataFrame(dates, columns=["date"])
        df["date"] = pd.to_datetime(df["date"])
        group_by = 'M' if unit == "months" else 'D'
        df_grouped = df.groupby(df["date"].dt.to_period(group_by)).size().reset_index(name="order_count")
        df_grouped["date"] = df_grouped["date"].astype(str)

        plt.figure(figsize=(8, 4))
        plt.plot(df_grouped["date"], df_grouped["order_count"], marker='o')
        title = f"{display_status} Orders Trend"
        if customer_name:
            title += f" - {customer_name.title()}"
        plt.title(title)
        plt.xlabel("Month" if unit == "months" else "Date")
        plt.ylabel("Number of Orders")
        plt.xticks(rotation=45)
        plt.tight_layout()

        os.makedirs("static/graphs", exist_ok=True)
        filename = f"{display_status.lower()}_orders_graph"
        if customer_name:
            filename += f"_{customer_name.replace(' ', '_')}"
        filename += ".png"
        filepath = os.path.join("static/graphs", filename)
        plt.savefig(filepath)
        plt.close()

        public_url = f"http://16.171.255.49:3000/static/files/{filename}"
        dispatcher.utter_message(f"Here's the **{display_status}** order trend for the last {duration} {unit}:")
        dispatcher.utter_message(image=public_url)
        dispatcher.utter_message(f"[Click here to view the graph]({public_url})")
        dispatcher.utter_message(custom={"graph_url": public_url})
        print(f"[TIME] action_order_trend_graph_by_status took {(time.time() - start_time):.2f} seconds")
        return []
class ActionStakeholderDistribution(Action):
    def name(self) -> Text:
        return "action_stakeholder_distribution"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = time.time()
        customer_input = tracker.get_slot("customer_name")
        if not customer_input:
            customer_input = next(tracker.get_latest_entity_values("customer_name"), None)

        match_stage = {}
        if customer_input:
            match_stage = {
                "start.contact.name": {"$regex": customer_input, "$options": "i"}
            }

        delivery_statuses = ["delivered", "delivered_to_neighbour", "delivered_to_watchman"]

        stakeholder_pipeline = []
        if match_stage:
            stakeholder_pipeline.append({"$match": match_stage})
        stakeholder_pipeline += [
            {
                "$project": {
                    "deliveredEvent": {
                        "$first": {
                            "$filter": {
                                "input": "$orderStatusEvents",
                                "as": "event",
                                "cond": {
                                    "$in": ["$$event.status", delivery_statuses]
                                }
                            }
                        }
                    },
                    "orderId": 1
                }
            },
            {
                "$match": {
                    "deliveredEvent": {"$ne": None}
                }
            },
            {
                "$group": {
                    "_id": "$deliveredEvent.stakeholderType",
                    "count": {"$sum": 1}
                }
            }
        ]

        total_orders_pipeline = []
        if match_stage:
            total_orders_pipeline.append({"$match": match_stage})
        total_orders_pipeline += [
            {
                "$match": {
                    "orderStatusEvents": {
                        "$elemMatch": {
                            "status": {"$in": delivery_statuses}
                        }
                    }
                }
            },
            {
                "$count": "total"
            }
        ]

        try:
            stakeholder_data = list(collection.aggregate(stakeholder_pipeline))
            total_count_data = list(collection.aggregate(total_orders_pipeline))
        except Exception as e:
            dispatcher.utter_message("Error while querying the database.")
            print(f"[ERROR] {e}")
            return []

        total_delivered = total_count_data[0]["total"] if total_count_data else 0

        if not stakeholder_data:
            msg = "No delivered orders found"
            if customer_input:
                msg += f" for customer **{customer_input}**."
            dispatcher.utter_message(msg)
            return []

        response = "**Stakeholder Distribution for Delivered Orders**"
        if customer_input:
            response += f" for **{customer_input.title()}**"
        response += ":\n\n"

        response += f"{'Stakeholder Type':<25} {'Order Count':<12}\n"
        response += f"{'-'*25} {'-'*12}\n"

        for item in stakeholder_data:
            st_type = item["_id"] or "Unknown"
            count = item["count"]
            response += f"{st_type:<25} {count:<12}\n"

        response += f"\n**Total Delivered Orders:** {total_delivered}"

        dispatcher.utter_message(response)
        dispatcher.utter_message(custom={"stakeholders": serialize_for_json(stakeholder_data), "total": total_delivered})
        print(f"[TIME] action_stakeholder_distribution took {(time.time() - start_time):.2f} seconds")
        return []

class ActionGetPendingOrdersByPickupCity(Action): 
    def name(self) -> Text:
        return "action_get_pending_orders_by_pickup_city"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        from collections import defaultdict
        import os
        import pandas as pd

        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "")
        pickup_location = extract_pickup_city(message_text)

        if not customer_input:
            dispatcher.utter_message("Please provide a customer name to fetch the orders.")
            return []
        if not pickup_location:
            dispatcher.utter_message("Please also mention the pickup location (city).")
            return []

        PENDING_STATUSES = [
            "at_fm_agent_hub", "at_lm_agent_hub", "fm_package_verified",
            "handed_over_to_agent", "handed_over_to_midmile_shipper",
            "lm_delayed", "out_for_delivery", "out_for_pickup", "pickup_failed"
        ]

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        try:
            query = {
                "$and": [
                    {"orderStatus": {"$in": PENDING_STATUSES}},
                    {"$or": [{"start.contact.name": {"$regex": name, "$options": "i"}} for name in matched_customers]},
                    {"start.address.mapData.city": {"$regex": f"^{pickup_location}$", "$options": "i"}}
                ]
            }

            matched_orders = list(collection.find(query))
            if not matched_orders:
                dispatcher.utter_message(f"No pending orders found for **{customer_input}** from **{pickup_location}**.")
                return []

            now = datetime.now(pytz.utc)
            orders_by_city = defaultdict(list)
            city_counts = {}
            all_rows = []

            for order in matched_orders:
                pickup_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
                drop_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
                order_id = order.get("orderId", "N/A")
                status_raw = order.get("orderStatus", "unknown")
                status = get_aesthetic_status(status_raw)

                created_at = order.get("createdAt")
                if isinstance(created_at, int):
                    created_at = datetime.fromtimestamp(created_at / 1000, pytz.utc)
                elif isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = pytz.utc.localize(created_at)

                booking_date = created_at.strftime('%Y-%m-%d') if created_at else "N/A"
                tat_days = (now - created_at).days if created_at else "N/A"

                record = {
                    "Pickup City": pickup_city,
                    "Order ID": order_id,
                    "Date": booking_date,
                    "TAT (days)": tat_days,
                    "Drop City": drop_city,
                    "Status": status
                }

                orders_by_city[pickup_city].append(record)
                city_counts[pickup_city] = city_counts.get(pickup_city, 0) + 1
                all_rows.append(record)

            msg_lines = [f"**Pending Orders for {customer_input.title()} from {pickup_location.title()}**:\n"]

            for city, orders in orders_by_city.items():
                msg_lines.append(f"\n **Location: {city}**")
                header = f"{'Order ID':<20} {'Date':<12} {'TAT':<6} {'Drop City':<20} {'Status':<30}"
                msg_lines.append(header)
                msg_lines.append("-" * len(header))

                for o in orders[:10]:
                    msg_lines.append(f"{o['Order ID']:<20} {o['Date']:<12} {str(o['TAT (days)']):<6} {o['Drop City']:<20} {o['Status']:<30}")

            msg_lines.append("\n**Total Pending Orders by Pickup Location:**")
            for city, count in city_counts.items():
                msg_lines.append(f"- {city}: {count}")

            dispatcher.utter_message("\n".join(msg_lines))

            df = pd.DataFrame(all_rows)
            os.makedirs("static/files", exist_ok=True)
            filename = "pickup_city_pending_orders.xlsx"
            filepath = os.path.join("static/files", filename)
            df.to_excel(filepath, index=False)

            public_url = f"http://16.171.255.49:3000/static/files/{filename}"
            dispatcher.utter_message(" Download full Excel report here:")
            dispatcher.utter_message(public_url)

        except Exception as e:
            dispatcher.utter_message(f" Error retrieving orders: {str(e)}")
            return []

        return []


class ActionGetCustomerPendingOrdersAllCities(Action):
    def name(self) -> Text:
        return "action_get_customer_pending_orders_all_cities"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        from collections import defaultdict
        import os
        import pandas as pd

        customer_input = tracker.get_slot("customer_name")
        if not customer_input:
            dispatcher.utter_message("Please provide a customer name to fetch the orders.")
            return []

        PENDING_STATUSES = [
            "at_fm_agent_hub", "at_lm_agent_hub", "fm_package_verified",
            "handed_over_to_agent", "handed_over_to_midmile_shipper",
            "lm_delayed", "out_for_delivery", "out_for_pickup", "pickup_failed"
        ]

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            return []

        try:
            query = {
                "$and": [
                    {"orderStatus": {"$in": PENDING_STATUSES}},
                    {"$or": [{"start.contact.name": {"$regex": name, "$options": "i"}} for name in matched_customers]}
                ]
            }

            matched_orders = list(collection.find(query))
            if not matched_orders:
                dispatcher.utter_message(f"No pending orders found for **{customer_input}**.")
                return []

            now = datetime.now(pytz.utc)
            orders_by_city = defaultdict(list)
            city_counts = {}
            all_rows = []

            for order in matched_orders:
                pickup_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
                drop_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
                order_id = order.get("orderId", "N/A")
                status_raw = order.get("orderStatus", "unknown")
                status = get_aesthetic_status(status_raw)

                created_at = order.get("createdAt")
                if isinstance(created_at, int):
                    created_at = datetime.fromtimestamp(created_at / 1000, pytz.utc)
                elif isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = pytz.utc.localize(created_at)

                booking_date = created_at.strftime('%Y-%m-%d') if created_at else "N/A"
                tat_days = (now - created_at).days if created_at else "N/A"

                record = {
                    "Pickup City": pickup_city,
                    "Order ID": order_id,
                    "Date": booking_date,
                    "TAT (days)": tat_days,
                    "Drop City": drop_city,
                    "Status": status
                }

                orders_by_city[pickup_city].append(record)
                city_counts[pickup_city] = city_counts.get(pickup_city, 0) + 1
                all_rows.append(record)

            msg_lines = [f"**Pending Orders for {customer_input.title()}**:\n"]

            for city, orders in orders_by_city.items():
                msg_lines.append(f"\n **Location: {city}**")
                header = f"{'Order ID':<20} {'Date':<12} {'TAT':<6} {'Drop City':<20} {'Status':<30}"
                msg_lines.append(header)
                msg_lines.append("-" * len(header))

                for o in orders[:10]:
                    msg_lines.append(f"{o['Order ID']:<20} {o['Date']:<12} {str(o['TAT (days)']):<6} {o['Drop City']:<20} {o['Status']:<30}")

            msg_lines.append("\n **Total Pending Orders by Location:**")
            for city, count in city_counts.items():
                msg_lines.append(f"- {city}: {count}")

            dispatcher.utter_message("\n".join(msg_lines))

            df = pd.DataFrame(all_rows)
            os.makedirs("static/files", exist_ok=True)
            filename = "customer_pending_orders_by_city.xlsx"
            filepath = os.path.join("static/files", filename)
            df.to_excel(filepath, index=False)

            public_url = f"http://16.171.255.49:3000/static/files/{filename}"
            dispatcher.utter_message("Download full Excel report here:")
            dispatcher.utter_message(public_url)

        except Exception as e:
            dispatcher.utter_message(f" Error retrieving orders: {str(e)}")
            return []

        return []


class ActionGetPendingOrdersMatrix(Action):
    def name(self) -> Text:
        return "action_get_pending_orders_matrix"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        start_time = datetime.now()
        from collections import defaultdict
        import os
        import pandas as pd

        PENDING_STATUSES = [
            "at_fm_agent_hub", "at_lm_agent_hub", "fm_package_verified",
            "handed_over_to_agent", "handed_over_to_midmile_shipper",
            "lm_delayed", "out_for_delivery", "out_for_pickup", "pickup_failed"
        ]

        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "").lower()
        use_destination = any(word in message_text for word in ["destination", "drop", "to city"])

        try:
            query = {"orderStatus": {"$in": PENDING_STATUSES}}

            if customer_input:
                all_names = collection.distinct("start.contact.name")
                matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]
                if not matched_customers:
                    dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
                    return []

                customer_conditions = [{"start.contact.name": {"$regex": name, "$options": "i"}} for name in matched_customers]
                query = {"$and": [query, {"$or": customer_conditions}]}

            orders = list(collection.find(query))
            if not orders:
                msg = f"No pending orders found"
                if customer_input:
                    msg += f" for **{customer_input}**"
                dispatcher.utter_message(msg + ".")
                return []

            pivot_data = defaultdict(lambda: defaultdict(int))

            for order in orders:
                address_key = "end" if use_destination else "start"
                city = order.get(address_key, {}).get("address", {}).get("mapData", {}).get("city", "Unknown")

                created_at = order.get("createdAt", "")
                if isinstance(created_at, int):
                    created_at = datetime.fromtimestamp(created_at / 1000, pytz.utc)
                elif isinstance(created_at, str):
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                elif isinstance(created_at, datetime) and created_at.tzinfo is None:
                    created_at = pytz.utc.localize(created_at)

                if not isinstance(created_at, datetime):
                    continue

                date_str = created_at.strftime('%d/%m/%Y')
                pivot_data[city][date_str] += 1

            all_dates = sorted({date for city_data in pivot_data.values() for date in city_data})
            city_list = sorted(pivot_data.keys())

            message = f"**Pending Orders Matrix**\n"
            if customer_input:
                message += f"Filtered for customer: **{customer_input.title()}**\n"
            message += f"Grouped by **{'Destination' if use_destination else 'Pickup'} City** and Date.\n\n"

            header = f"{'Location':<20}" + "".join(f"{date:<12}" for date in all_dates) + f"{'Total':<8}\n"
            message += header + "-" * len(header) + "\n"

            rows = []
            grand_total = 0
            for city in city_list:
                row_data = {"Location": city}
                total = 0
                line = f"{city:<20}"
                for date in all_dates:
                    count = pivot_data[city].get(date, 0)
                    row_data[date] = count
                    line += f"{count:<12}"
                    total += count
                row_data["Total"] = total
                rows.append(row_data)
                grand_total += total
                line += f"{total:<8}"
                message += line + "\n"

            message += "-" * len(header) + "\n"
            message += f"{'Grand Total':<20}" + "".join(" " * 12 for _ in all_dates) + f"{grand_total:<8}\n"

            dispatcher.utter_message(message)

            df = pd.DataFrame(rows)
            os.makedirs("static/files", exist_ok=True)
            filename = "pending_orders_matrix.xlsx"
            filepath = os.path.join("static/files", filename)
            df.to_excel(filepath, index=False)

            public_url = f"http://16.171.255.49:3000/static/files/{filename}"
            dispatcher.utter_message("Download the full matrix here:")
            dispatcher.utter_message(public_url)

        except Exception as e:
            dispatcher.utter_message(f"Error generating matrix: {str(e)}")
            return []

        print(f"[TIME] action_get_pending_orders_matrix took {(datetime.now() - start_time).total_seconds():.2f} seconds")
        return []


class ActionDefaultFallback(Action):
    def name(self):
        return "action_default_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="I'm sorry, I didn't quite understand that. Can you rephrase or ask something else?")
        return []