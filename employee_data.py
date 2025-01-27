from datetime import datetime
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

    def process_natural_language(self, user_input: str, employee_name: str) -> dict:
        """Process natural language input using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a leave management assistant that handles leave requests and balance queries.

                        Available leave types:
                        - Sick Leave (includes medical leave, health-related absence, doctor visits)
                        - Annual Leave (includes vacation, holiday, personal time, time off)
                        - Maternity Leave (includes pregnancy leave, parental leave)

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
                        - Start Date: YYYY-MM-DD format
                        Example: {"intent": "request_leave", "leave_type": "Annual Leave", "days": 3, "start_date": "2024-02-01"}

                        3. For cancellations:
                        - Intent: "cancel_leave"
                        - Leave Type: map to standard type
                        - Start Date: YYYY-MM-DD format

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
        """Process a leave request."""
        try:
            # Validate date format
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            return "Invalid date format. Please use YYYY-MM-DD format."

        if employee_name not in self.employees:
            return f"Employee {employee_name} not found."

        if leave_type not in self.employees[employee_name]:
            return f"Invalid leave type: {leave_type}"

        if not isinstance(days, (int, float)) or days <= 0:
            return "Number of days must be a positive number."

        current_balance = self.employees[employee_name][leave_type]
        if current_balance < days:
            return f"Insufficient {leave_type} balance. You have {current_balance} days available."

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
                }
            }
            with open("employees.json", 'w') as file:
                json.dump(sample_data, file, indent=4)

        lms = LeaveManagementSystem("employees.json")

        print("Welcome to the Leave Management System!")
        print("\nAvailable leave types:")
        for leave_type in lms.LEAVE_TYPES:
            print(f"- {leave_type}")

        print("\nPlease enter your name:")
        employee_name = input().strip()

        if employee_name not in lms.employees:
            print(f"Employee {employee_name} not found.")
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
            elif response["intent"] == "view_history":
                print(lms.view_history(employee_name))
            else:
                print("I couldn't process your request. Please try again.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()
