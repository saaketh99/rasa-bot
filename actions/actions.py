import re
import time
from typing import Any, Text, Dict, List, Optional, Tuple
from dateutil import parser
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from pymongo import MongoClient
from rapidfuzz import process, fuzz
from datetime import datetime
from datetime import datetime, timedelta
from collections import Counter

client = MongoClient("mongodb+srv://ordersDbAdmin:LuiQu4KLLM0KXvQX@orders-cluster.jbais.mongodb.net/")
db = client["orders-db"]
collection = db["SaaS_Orders"]

sender_cities = collection.distinct("start.address.mapData.city")
receiver_cities = collection.distinct("end.address.mapData.city")
known_cities = list(set(sender_cities + receiver_cities))
known_statuses = list(collection.distinct("orderStatus"))

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


class ActionrouteOrder(Action):
    def name(self) -> Text:
        return "action_route"

    def run(self, dispatcher, tracker, domain):
        start_time = time.time()
        message_text = tracker.latest_message.get("text", "")
        pickup, drop = extract_cities_by_keywords(message_text)

        if not pickup or not drop:
            dispatcher.utter_message("Please provide both pickup and drop locations.")
            print(f"[TIME] action_route took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "start.address.mapData.city": {"$regex": f"^{pickup}$", "$options": "i"},
            "end.address.mapData.city": {"$regex": f"^{drop}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found from {pickup} to {drop}.")
            print(f"[TIME] action_route took {time.time() - start_time:.2f} seconds")
            return []

        message = f"Orders from {pickup} to {drop}:\n"
        for order in matched_orders:
            created_date = order.get("createdAt")
            booking_date = created_date.strftime('%Y-%m-%d') if hasattr(created_date, 'strftime') else str(created_date)
            message += (
                f"Order ID: {order.get('sm_orderid', 'N/A')} | "
                f"Sender: {order.get('start', {}).get('contact', {}).get('name', 'N/A')} | "
                f"Booking Date: {booking_date}\n"
            )

        dispatcher.utter_message(message)
        print(f"[TIME] action_route took {time.time() - start_time:.2f} seconds")
        return []

class ActionFordestination(Action):
    def name(self) -> Text:
        return "action_cx_destination"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        start_time = time.time()
        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "")
        destination = extract_destination_city(message_text)

        if not customer_input or not destination:
            dispatcher.utter_message("Please provide both customer name and destination.")
            print(f"[TIME] action_cx_destination took {time.time() - start_time:.2f} seconds")
            return []

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            print(f"[TIME] action_cx_destination took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "end.address.mapData.city": {"$regex": f"^{destination}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message("No orders found for the given customer to that destination.")
            print(f"[TIME] action_cx_destination took {time.time() - start_time:.2f} seconds")
            return []

        message = f"Orders for '{customer_input}' delivered to {destination}:\n"
        for order in matched_orders:
            sender_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            recipient_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            order_id = order.get("sm_orderid", "N/A")
            message += f"- Order ID: {order_id} | {sender_city} → {recipient_city}\n"

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)
        print(f"[TIME] action_cx_destination took {time.time() - start_time:.2f} seconds")
        return []

class ActionCxOrder(Action):
    def name(self) -> Text:
        return "action_cx_date"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_time = time.time()
        customer_input = tracker.get_slot("customer_name")
        message_text = tracker.latest_message.get("text", "")
        s_date, e_date = extract_dates_from_text(message_text)

        if not customer_input or not s_date or not e_date:
            dispatcher.utter_message("Please provide both customer name and valid start/end dates.")
            print(f"[TIME] action_cx_date took {time.time() - start_time:.2f} seconds")
            return []

        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            print(f"[TIME] action_cx_date took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "createdAt": {"$gte": s_date, "$lte": e_date}
        }))

        if not matched_orders:
            dispatcher.utter_message("No orders found for the given customer in the provided date range.")
            print(f"[TIME] action_cx_date took {time.time() - start_time:.2f} seconds")
            return []

        message = f" Orders for **{customer_input}** from **{s_date}** to **{e_date}**:\n"
        for order in matched_orders:
            order_id = order.get("sm_orderid", "N/A")
            sender_city = order.get("start", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")
            recipient_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")

            message += f"- Order ID: {order_id} | {sender_city} → {recipient_city}\n"

        message += f"\n Total orders: {len(matched_orders)}"
        dispatcher.utter_message(message)
        print(f"[TIME] action_cx_date took {time.time() - start_time:.2f} seconds")
        return []

class ActionGetOrdersByStatus(Action):
    def name(self) -> Text:
        return "action_get_orders_by_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_time = time.time()
        message_text = tracker.latest_message.get("text", "").lower()

        delivered_statuses = ["delivered", "delivered_at_security", "delivered_at_neighbor"]
        exclude_statuses = set(["cancelled"] + delivered_statuses)

        matched_orders = []
        custom_filter = {}

        if any(keyword in message_text for keyword in ["delivered"]):
    
            custom_filter = {
                "orderStatus": {"$in": delivered_statuses}
            }
        elif any(keyword in message_text for keyword in ["pending", "undelivered", "not delivered", "delayed", "waiting"]):
            non_delivered_statuses = [s for s in known_statuses if s not in exclude_statuses]
            custom_filter = {
                "orderStatus": {"$in": non_delivered_statuses}
            }
        else:
            status = fuzzy_status_match(message_text)
            if not status:
                dispatcher.utter_message("Sorry, I couldn't identify the delivery status you're looking for.")
                print(f"[TIME] action_get_orders_by_status took {time.time() - start_time:.2f} seconds")
                return []

            custom_filter = {
                "orderStatus": {"$regex": f"^{status}$", "$options": "i"}
            }

        matched_orders = list(collection.find(custom_filter))

        if not matched_orders:
            dispatcher.utter_message("No orders found for the requested delivery status.")
            print(f"[TIME] action_get_orders_by_status took {time.time() - start_time:.2f} seconds")
            return []

        message = "Orders:\n"
        for order in matched_orders:
            order_id = order.get("sm_orderid", "N/A")
            customer_name = order.get("start", {}).get("contact", {}).get("name", "Unknown")
            booking_date_raw = order.get("createdAt", None)
            booking_date = booking_date_raw.strftime('%Y-%m-%d') if hasattr(booking_date_raw, 'strftime') else str(booking_date_raw)
            status = order.get("orderStatus", order.get("Order Status", "Unknown"))

            message += f"- Order ID: {order_id} | Customer: {customer_name} | Status: {status} | Date: {booking_date}\n"

        message += f"\nTotal orders: {len(matched_orders)}"
        dispatcher.utter_message(message)
        print(f"[TIME] action_get_orders_by_status took {time.time() - start_time:.2f} seconds")
        return []


class ActionFetchByMetadata(Action):
    def name(self) -> Text:
        return "action_fetch_by_metadata"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_time = time.time()
        message = tracker.latest_message.get("text", "").lower()

        if "inserted by" in message:
            inserted_by = message.split("inserted by")[-1].strip()
        else:
            dispatcher.utter_message("Please specify who inserted the data.")
            print(f"[TIME] action_fetch_by_metadata took {time.time() - start_time:.2f} seconds")
            return []

        matched_orders = list(collection.find({
            "metadata.inserted_by": {"$regex": f"^{inserted_by}$", "$options": "i"}
        }))

        if not matched_orders:
            dispatcher.utter_message(f"No orders found inserted by '{inserted_by}'.")
            print(f"[TIME] action_fetch_by_metadata took {time.time() - start_time:.2f} seconds")
            return []

        response = f"Orders inserted by '{inserted_by}':\n"
        for order in matched_orders:
            response += f"- Order ID: {order['Order ID']} | Sender: {order['Sender Name']}\n"

        dispatcher.utter_message(response)
        print(f"[TIME] action_fetch_by_metadata took {time.time() - start_time:.2f} seconds")
        return []

class ActionGetOrderStatus(Action):
    def name(self) -> Text:
        return "action_get_order_status"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_time = time.time()
        order_id = None
        for ent in tracker.latest_message.get("entities", []):
            if ent.get("entity") == "order_id":
                order_id = ent.get("value")
                break

        if not order_id:
            dispatcher.utter_message("Please provide the order ID to check its status.")
            print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
            return []

        order = collection.find_one({
            "$or": [{"sm_orderid": order_id}, {"Order ID": order_id}]
        })

        if not order:
            dispatcher.utter_message(f"No order found with ID {order_id}.")
            print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
            return []

        status = order.get("orderStatus", order.get("Order Status", "Unknown"))
        message = f"Status of order ID {order_id}: {status}"

        if status.lower() == "delivered":
            delivery_event = next((e for e in order.get("orderStatusEvents", []) 
                                   if e.get("status", "").lower() == "delivered"), None)
            if delivery_event:
                timestamp = delivery_event.get("timeStamp", {})
                try:
                    if "$date" in timestamp and "$numberLong" in timestamp["$date"]:
                        ts = int(timestamp["$date"]["$numberLong"])
                        delivery_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                        message += f". It was delivered on {delivery_date}."
                    else:
                        message += f". Delivery date: {timestamp}"
                except Exception:
                    message += f". Delivery date: {timestamp}"
            else:
                message += ". Delivery date not recorded."

        dispatcher.utter_message(message)
        print(f"[TIME] action_get_order_status took {time.time() - start_time:.2f} seconds")
        return []

class ActionGetOrdersByTAT(Action):
    def name(self) -> Text:
        return "action_get_orders_by_tat"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        start_time = time.time()
        message = tracker.latest_message.get("text", "").lower()
        match = re.search(r"\b(\d+)\s*(day|days)?\b", message)

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
                        "order_id": order.get("sm_orderid"),
                        "sender": order.get("start", {}).get("contact", {}).get("name"),
                        "booking_date": booking_ts.strftime('%Y-%m-%d'),
                        "delivery_date": delivery_ts.strftime('%Y-%m-%d'),
                        "tat": tat
                    })

        message = (
            f"Total delivered orders in DB: {total_delivered}\n"
            f"Delivered in {tat_days} days: {len(matching_orders)}\n\n"
        )

        for o in matching_orders:
            message += (
                f"Order ID: {o['order_id']} | Sender: {o['sender']} | "
                f"Booking: {o['booking_date']} | Delivered: {o['delivery_date']} | "
                f"TAT: {o['tat']} days\n"
            )

        if not matching_orders:
            message += "No orders found matching the given TAT."

        dispatcher.utter_message(message)
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
            "delivered_at_neighbor"
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
            print(f"[TIME] action_pending_orders_past_days took {(datetime.now() - start_time).total_seconds():.2f} seconds")
            return []

        
        results = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "orderStatus": {"$nin": delivered_statuses + ["cancelled"]},
            "createdAt": {"$gte": date_cutoff}
        }))

        if not results:
            dispatcher.utter_message(f"No pending orders found for '{customer_input}' in the past {n_days} days.")
            print(f"[TIME] action_pending_orders_past_days took {(datetime.now() - start_time).total_seconds():.2f} seconds")
            return []

        message = f"Pending orders for **{customer_input}** in the past **{n_days}** days:\n"
        for order in results:
            order_id = order.get("sm_orderid", "N/A")
            status = order.get("orderStatus", "Unknown")
            created_at = order.get("createdAt")
            created_date = created_at.strftime('%Y-%m-%d') if hasattr(created_at, "strftime") else str(created_at)
            to_city = order.get("end", {}).get("address", {}).get("mapData", {}).get("city", "Unknown")

            message += f"- Order ID: {order_id} | Status: {status} | To: {to_city} | Created: {created_date}\n"

        message += f"\nTotal pending orders: {len(results)}"
        dispatcher.utter_message(message)
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
            print(f"[TIME] action_top_pincodes_by_customer took {time.time() - start_time:.2f} seconds")
            return []

    
        all_names = collection.distinct("start.contact.name")
        matched_customers = [name for name in all_names if customer_input.lower() in name.lower()]

        if not matched_customers:
            dispatcher.utter_message(f"No matching customers found for '{customer_input}'.")
            print(f"[TIME] action_top_pincodes_by_customer took {time.time() - start_time:.2f} seconds")
            return []


        orders = list(collection.find({
            "start.contact.name": {"$in": matched_customers},
            "end.address.mapData.pincode": {"$exists": True, "$ne": ""}
        }))

        if not orders:
            dispatcher.utter_message(f"No orders found for matching customers of '{customer_input}'.")
            print(f"[TIME] action_top_pincodes_by_customer took {time.time() - start_time:.2f} seconds")
            return []

    
        pincode_counter = Counter()
        for order in orders:
            pincode = order.get("end", {}).get("address", {}).get("mapData", {}).get("pincode")
            if pincode:
                pincode_counter[pincode] += 1

        top_pincodes = pincode_counter.most_common(10)

        if not top_pincodes:
            dispatcher.utter_message(f"No destination pincodes found for the matched customers.")
            print(f"[TIME] action_top_pincodes_by_customer took {time.time() - start_time:.2f} seconds")
            return []

        
        matched_names_str = ', '.join(matched_customers)
        message = f"Top 10 delivery pincodes for customers matching '{customer_input}':\n"
        message += f"Matched names: {matched_names_str}\n\n"
        for i, (pincode, count) in enumerate(top_pincodes, start=1):
            message += f"{i}. Pincode:{pincode}--{count} orders\n"

        dispatcher.utter_message(message)
        print(f"[TIME] action_top_pincodes_by_customer took {time.time() - start_time:.2f} seconds")
        return []