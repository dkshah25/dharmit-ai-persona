import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_EVENT_TYPE_ID = os.getenv("CAL_EVENT_TYPE_ID")
CAL_USERNAME = os.getenv("CAL_USERNAME")

def get_slots(start_date_str=None, end_date_str=None):
    """
    Fetch available slots.
    If CAL_API_KEY and CAL_EVENT_TYPE_ID are available, calls Cal.com.
    Otherwise, falls back to generating mock slots for testing.
    """
    # Parse dates or default to today + 7 days
    today = datetime.now()
    if not start_date_str:
        start_date = today
    else:
        try:
            start_date = datetime.fromisoformat(start_date_str.split('T')[0])
        except:
            start_date = today
            
    if not end_date_str:
        end_date = start_date + timedelta(days=7)
    else:
        try:
            end_date = datetime.fromisoformat(end_date_str.split('T')[0])
        except:
            end_date = start_date + timedelta(days=7)

    start_iso = start_date.strftime("%Y-%m-%dT00:00:00.000Z")
    end_iso = end_date.strftime("%Y-%m-%dT23:59:59.000Z")

    if CAL_API_KEY and CAL_EVENT_TYPE_ID:
        try:
            url = "https://api.cal.com/v2/slots"
            headers = {
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-09-04"
            }
            params = {
                "eventTypeId": int(CAL_EVENT_TYPE_ID),
                "start": start_iso,
                "end": end_iso
            }
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code == 200:
                slots_data = response.json().get("data", {})
                # Format slots nicely: a flat list of datetime strings
                all_slots = []
                for date, slots_list in slots_data.items():
                    for slot in slots_list:
                        all_slots.append(slot.get("start"))
                return sorted(all_slots)
            else:
                print(f"Cal.com API error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception calling Cal.com slots: {e}")

    # Fallback/Mock Slots implementation
    print("Using Mock Calendar Slots (Cal.com configuration not active or failed)")
    mock_slots = []
    current_day = start_date
    while current_day <= end_date:
        # Avoid weekends
        if current_day.weekday() < 5:
            # 10:00, 11:30, 14:00, 15:30 in user timezone
            hours = [10, 11, 14, 15]
            mins = [0, 30, 0, 30]
            for h, m in zip(hours, mins):
                slot_time = current_day.replace(hour=h, minute=m, second=0, microsecond=0)
                # Ensure it's in the future
                if slot_time > today:
                    mock_slots.append(slot_time.strftime("%Y-%m-%dT%H:%M:00.000Z"))
        current_day += timedelta(days=1)
    
    return sorted(mock_slots)[:20]

def create_booking(start_time, name, email, notes=""):
    """
    Creates a booking.
    Calls Cal.com if CAL_API_KEY and CAL_EVENT_TYPE_ID are set,
    otherwise returns a mock successful booking.
    """
    if CAL_API_KEY and CAL_EVENT_TYPE_ID:
        try:
            url = "https://api.cal.com/v2/bookings"
            headers = {
                "Authorization": f"Bearer {CAL_API_KEY}",
                "cal-api-version": "2024-08-13"
            }
            payload = {
                "eventTypeId": int(CAL_EVENT_TYPE_ID),
                "start": start_time,
                "attendee": {
                    "name": name,
                    "email": email,
                    "timeZone": "UTC"
                },
                "location": {
                    "type": "integration",
                    "integration": "cal-video"
                },
                "metadata": {
                    "notes": notes
                }
            }
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                data = response.json().get("data", {})
                return {
                    "success": True,
                    "booking_id": data.get("id"),
                    "start": data.get("start", start_time),
                    "name": data.get("attendees", [{}])[0].get("name", name),
                    "email": data.get("attendees", [{}])[0].get("email", email),
                    "status": "confirmed",
                    "cal_link": data.get("location", "")
                }
            else:
                print(f"Cal.com booking creation failed: {response.status_code} - {response.text}")
                return {"success": False, "error": response.text}
        except Exception as e:
            print(f"Exception creating Cal.com booking: {e}")
            return {"success": False, "error": str(e)}

    # Mock booking success response
    print("Using Mock Booking System")
    booking_id = int(datetime.now().timestamp())
    return {
        "success": True,
        "booking_id": booking_id,
        "start": start_time,
        "name": name,
        "email": email,
        "status": "confirmed",
        "cal_link": f"https://cal.com/{CAL_USERNAME or 'dkshah25'}/interview"
    }
