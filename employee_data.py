from datetime import datetime, timedelta
import json
from dotenv import load_dotenv
import os
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()


class LeaveManagementSystem:
    # Core leave types
    LEAVE_TYPES = [
        "Sick Leave",
        "Annual Leave",
        "Maternity Leave"
    ]

    def __init__(self, json_file_path: str):
        # Fetch API key from environment variable
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set!")
        self.client = OpenAI(api_key=api_key)

        # Initialize json_file_path as instance variable
        self.json_file_path = json_file_path

        try:
            # Load employee data from JSON file
            with open(json_file_path, 'r') as file:
                self.employees = json.load(file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Employee data file not found: {json_file_path}")
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON format in file: {json_file_path}")

        # Store leave history
        self.leave_history = {name: [] for name in self.employees.keys()}

    def validate_and_format_date(self, date_str: str) -> tuple[bool, str]:
        """Validate and format date strings, handling 'today' and various formats."""
        try:
            if date_str.lower() == 'today':
                return True, datetime.now().strftime("%Y-%m-%d")

            # Try various date formats
            for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%d-%m-%Y", "%d.%m.%Y"]:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return True, date_obj.strftime("%Y-%m-%d")  # Convert to standard format
                except ValueError:
                    continue

            return False, "Invalid date format. Please use YYYY-MM-DD, YYYY.MM.DD, DD-MM-YYYY, DD.MM.YYYY or 'today'"
        except Exception:
            return False, "Invalid date format. Please use YYYY-MM-DD, YYYY.MM.DD, DD-MM-YYYY, DD.MM.YYYY or 'today'"

    def check_leave_overlap(self, employee_name: str, new_start_date: str, days: int) -> bool:
        """
        Check if a new leave request overlaps with existing approved leaves.
        Returns True if there is an overlap, False otherwise.
        """
        # Convert new leave dates to datetime objects
        new_start = datetime.strptime(new_start_date, "%Y-%m-%d")
        new_end = new_start + timedelta(days=days - 1)  # -1 because start day counts as first day

        # Check against existing approved leaves
        for leave in self.leave_history[employee_name]:
            if leave["status"] != "approved":
                continue

            existing_start = datetime.strptime(leave["start_date"], "%Y-%m-%d")
            existing_end = existing_start + timedelta(days=leave["days"] - 1)

            # Check for overlap
            if (new_start <= existing_end and existing_start <= new_end):
                return True

        return False

    def process_natural_language(self, user_input: str, employee_name: str) -> dict:
        """Process natural language input using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a leave management assistant that handles leave requests and balance queries.

                        Available leave types:
                        - Sick Leave (includes medical leave, health-related absence, doctor visits)
                        - Annual Leave (includes vacation, holiday, personal time, time off)
                        - Maternity Leave (includes pregnancy leave, parental leave)

                        Date formats accepted:
                        - "today"
                        - YYYY-MM-DD
                        - YYYY.MM.DD
                        - DD-MM-YYYY
                        - DD.MM.YYYY

                        Extract the following from user queries:

                        1. For balance checks:
                        a) ALL leave balances:
                           - "Show all my leave balances"
                           - "How many leaves do I have?"
                           → {"intent": "check_balance", "leave_type": "all"}

                        b) SPECIFIC leave types:
                           - "How many sick days left?"
                           → {"intent": "check_balance", "leave_type": "Sick Leave"}

                        c) MULTIPLE SPECIFIC types:
                           - "Show my sick and annual leave"
                           → {"intent": "check_balance", "leave_type": ["Sick Leave", "Annual Leave"]}

                        2. For leave requests:
                        - Intent: "request_leave"
                        - Leave Type: map to one of the three standard types
                        - Days: positive integer
                        - Start Date: Parse any supported date format
                        Examples: 
                        - "I want 3 days sick leave starting today"
                        → {"intent": "request_leave", "leave_type": "Sick Leave", "days": 3, "start_date": "today"}
                        - "Book annual leave for 2 days from 15.01.2024"
                        → {"intent": "request_leave", "leave_type": "Annual Leave", "days": 2, "start_date": "15.01.2024"}

                        3. For cancellations:
                        Extract these fields:
                        - Intent: "cancel_leave"
                        - Leave Type: map to standard type
                        - Start Date: Parse any supported date format

                        Example cancellation requests:
                        - "Cancel my sick leave for today"
                        → {"intent": "cancel_leave", "leave_type": "Sick Leave", "start_date": "today"}
                        - "Cancel annual leave starting 15.01.2024"
                        → {"intent": "cancel_leave", "leave_type": "Annual Leave", "start_date": "15.01.2024"}

                        4. For viewing history:
                        - Intent: "view_history"

                        Always map varied terms to standard types:
                        - Medical/health/doctor → "Sick Leave"
                        - Vacation/holiday/personal → "Annual Leave"
                        - Pregnancy/parental → "Maternity Leave"
                        """
                    },
                    {
                        "role": "user",
                        "content": f"Employee context: {employee_name}. Query: {user_input}"
                    }
                ],
                temperature=0.1  # Low temperature for consistent categorization
            )

            parsed_response = json.loads(response.choices[0].message.content)

            # Validate leave types
            if "leave_type" in parsed_response:
                if isinstance(parsed_response["leave_type"], list):
                    # For multiple leave type requests
                    for leave_type in parsed_response["leave_type"]:
                        if leave_type not in self.LEAVE_TYPES:
                            return {
                                "intent": "error",
                                "message": f"Invalid leave type: {leave_type}"
                            }
                elif parsed_response["leave_type"] != "all" and parsed_response["leave_type"] not in self.LEAVE_TYPES:
                    return {
                        "intent": "error",
                        "message": f"Invalid leave type. Available types are: {', '.join(self.LEAVE_TYPES)}"
                    }

            # Validate required fields for leave requests
            if parsed_response.get("intent") == "request_leave":
                required_fields = ["leave_type", "days", "start_date"]
                missing_fields = [field for field in required_fields if field not in parsed_response]
                if missing_fields:
                    return {
                        "intent": "error",
                        "message": f"Missing required information: {', '.join(missing_fields)}"
                    }

            # Validate required fields for cancel requests
            if parsed_response.get("intent") == "cancel_leave":
                required_fields = ["leave_type", "start_date"]
                missing_fields = [field for field in required_fields if field not in parsed_response]
                if missing_fields:
                    return {
                        "intent": "error",
                        "message": f"Missing required information for cancellation: {', '.join(missing_fields)}"
                    }

            return parsed_response

        except Exception as e:
            return {"intent": "error", "message": f"Error processing request: {str(e)}"}

    def check_leave_balance(self, employee_name: str, leave_type: str | list = "all") -> str:
        """Check leave balance for an employee."""
        if employee_name not in self.employees:
            return f"Employee {employee_name} not found."

        balance = self.employees[employee_name]

        # Handle multiple specific leave types
        if isinstance(leave_type, list):
            return f"Leave balance for {employee_name}:\n" + \
                "\n".join([f"- {lt}: {balance[lt]} days" for lt in leave_type])

        # Handle single leave type
        if leave_type != "all":
            if leave_type not in balance:
                return f"Invalid leave type: {leave_type}"
            return f"Current {leave_type} balance for {employee_name}: {balance[leave_type]} days"

        # Handle all leave types
        return f"Current leave balance for {employee_name}:\n" + \
            "\n".join([f"- {lt}: {balance[lt]} days" for lt in balance.keys()])

    def request_leave(self, employee_name: str, leave_type: str, days: int, start_date: str) -> str:
        """Process a leave request with overlap checking."""
        if employee_name not in self.employees:
            return f"Employee {employee_name} not found."

        if leave_type not in self.employees[employee_name]:
            return f"Invalid leave type: {leave_type}"

        # Validate and format date
        is_valid, result = self.validate_and_format_date(start_date)
        if not is_valid:
            return result
        start_date = result

        if not isinstance(days, (int, float)) or days <= 0:
            return "Number of days must be a positive number."

        current_balance = self.employees[employee_name][leave_type]
        if current_balance < days:
            return f"Insufficient {leave_type} balance. You have {current_balance} days available."

        # Check for overlapping leaves
        if self.check_leave_overlap(employee_name, start_date, days):
            return f"Cannot approve leave: You already have approved leave during this period."

        # Process leave request
        self.employees[employee_name][leave_type] -= days

        # Record in history
        leave_record = {
            "type": leave_type,
            "days": days,
            "start_date": start_date,
            "status": "approved",
            "request_date": datetime.now().strftime("%Y-%m-%d")
        }
        self.leave_history[employee_name].append(leave_record)

        # Save updated state
        self.save_state()

        return f"Leave request approved. {days} days of {leave_type} starting from {start_date}."

    def cancel_leave(self, employee_name: str, leave_type: str, start_date: str) -> str:
        """Cancel a previously approved leave request."""
        if employee_name not in self.employees:
            return f"Employee {employee_name} not found."

        if leave_type not in self.LEAVE_TYPES:
            return f"Invalid leave type: {leave_type}"

        # Validate and format date
        is_valid, result = self.validate_and_format_date(start_date)
        if not is_valid:
            return result
        start_date = result

        # Find all approved leaves for the employee
        approved_leaves = [
            (index, leave) for index, leave in enumerate(self.leave_history[employee_name])
            if leave["status"] == "approved"
        ]

        if not approved_leaves:
            return f"No approved leaves found for {employee_name}"

        # Find matching leave request
        matching_leaves = [
            (idx, leave) for idx, leave in approved_leaves
            if leave["type"] == leave_type and leave["start_date"] == start_date
        ]

        if not matching_leaves:
            # If no exact match, show available leaves that could be cancelled
            available_leaves = [
                f"- {leave['type']} starting {leave['start_date']} ({leave['days']} days)"
                for _, leave in approved_leaves
            ]

            return (f"No approved {leave_type} found starting on {start_date}\n"
                    f"Available leaves that can be cancelled:\n" +
                    "\n".join(available_leaves))

        # Cancel the leave and restore the balance
        index, leave_to_cancel = matching_leaves[0]
        self.employees[employee_name][leave_type] += leave_to_cancel["days"]
        self.leave_history[employee_name][index]["status"] = "cancelled"
        self.save_state()

        return (f"Successfully cancelled {leave_to_cancel['days']} days of {leave_type} "
                f"starting from {start_date}. Updated {leave_type} balance: "
                f"{self.employees[employee_name][leave_type]} days.")

    def view_history(self, employee_name: str) -> str:
        """View leave history for an employee."""
        if employee_name not in self.leave_history:
            return f"No history found for employee: {employee_name}"

        if not self.leave_history[employee_name]:
            return f"No leave records found for {employee_name}"

        history = self.leave_history[employee_name]
        response = f"Leave history for {employee_name}:\n"
        for record in history:
            response += f"- {record['type']}: {record['days']} days from {record['start_date']} ({record['status']})\n"
        return response

    def save_state(self):
        """Save the current state of employees back to the JSON file."""
        try:
            with open(self.json_file_path, 'w') as file:
                json.dump(self.employees, file, indent=4)
        except Exception as e:
            print(f"Error saving state: {str(e)}")


def main():
    try:
        # Create a sample employees.json file if it doesn't exist
        if not os.path.exists("employees.json"):
            sample_data = {
                "Alice": {
                    "Sick Leave": 5,
                    "Annual Leave": 7,
                    "Maternity Leave": 0
                },
                "Bob": {
                    "Sick Leave": 8,
                    "Annual Leave": 6,
                    "Maternity Leave": 0
                },
                "Charlie": {
                    "Sick Leave": 2,
                    "Annual Leave": 12,
                    "Maternity Leave": 0
                },
                "Eva": {
                    "Sick Leave": 10,
                    "Annual Leave": 15,
                    "Maternity Leave": 0
                }
            }
            with open("employees.json", 'w') as file:
                json.dump(sample_data, file, indent=4)

        lms = LeaveManagementSystem("employees.json")

        print("Welcome to the Leave Management System!")
        print("\nAvailable leave types:")
        for leave_type in lms.LEAVE_TYPES:
            print(f"- {leave_type}")

        # Add name retry logic with case-insensitive matching
        max_attempts = 3
        attempts = 0
        employee_name = None

        # Create case-insensitive mapping of names
        name_mapping = {name.lower(): name for name in lms.employees.keys()}

        while attempts < max_attempts:
            if attempts > 0:
                remaining = max_attempts - attempts
                print(f"\nPlease try again. {remaining} {'attempt' if remaining == 1 else 'attempts'} remaining.")

            print("\nPlease enter your name:")
            entered_name = input().strip()

            # Check for case-insensitive match
            if entered_name.lower() in name_mapping:
                employee_name = name_mapping[entered_name.lower()]  # Get the correct case version
                break

            print(f"Employee {entered_name} not found.")
            print("Valid employees are: " + ", ".join(lms.employees.keys()))
            attempts += 1

        if attempts >= max_attempts:
            print("\nMaximum attempts reached. Please contact your administrator for assistance.")
            return

        print(f"Welcome, {employee_name}! How can I assist you with your leave?")
        while True:
            print("\nEnter your query (or type 'exit' to quit):")
            user_query = input().strip()

            if user_query.lower() == "exit":
                print("Goodbye!")
                break

            # Process user query
            response = lms.process_natural_language(user_query, employee_name)
            if response["intent"] == "error":
                print(response["message"])
            elif response["intent"] == "check_balance":
                print(lms.check_leave_balance(employee_name, response["leave_type"]))
            elif response["intent"] == "request_leave":
                print(lms.request_leave(
                    employee_name,
                    response["leave_type"],
                    response["days"],
                    response["start_date"]
                ))
            elif response["intent"] == "cancel_leave":
                print(lms.cancel_leave(
                    employee_name,
                    response["leave_type"],
                    response["start_date"]
                ))
            elif response["intent"] == "view_history":
                print(lms.view_history(employee_name))
            else:
                print("I couldn't process your request. Please try again.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
