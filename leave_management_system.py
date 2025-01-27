from datetime import datetime
import json
from dotenv import load_dotenv
import os
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()


class LeaveManagementSystem:
    def __init__(self, json_file_path: str):  # Fixed method name from _init to __init__
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

    def save_state(self):
        """Save the current state of employees back to the JSON file."""
        try:
            with open(self.json_file_path, 'w') as file:
                json.dump(self.employees, file, indent=4)
        except Exception as e:
            print(f"Error saving state: {str(e)}")

    def process_natural_language(self, user_input: str, employee_name: str) -> dict:
        """Process natural language input using OpenAI API."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": """
                        You are a leave management assistant. Extract the following information from user queries:
                        - Intent (check_balance, request_leave, cancel_leave, view_history)
                        - Leave type (if applicable)
                        - Number of days (if applicable)
                        - Start date (if applicable)
                        Return JSON format only, no other text.
                        Example: {"intent": "request_leave", "leave_type": "Sick Leave", "days": 3, "start_date": "2024-02-01"}
                        """
                    },
                    {"role": "user", "content": user_input}
                ]
            )

            parsed_response = json.loads(response.choices[0].message.content)
            # Validate required fields based on intent
            if parsed_response.get("intent") == "request_leave":
                required_fields = ["leave_type", "days", "start_date"]
                if not all(field in parsed_response for field in required_fields):
                    return {"intent": "error", "message": "Missing required information for leave request"}

            return parsed_response
        except Exception as e:
            return {"intent": "error", "message": f"Error processing request: {str(e)}"}

    def check_leave_balance(self, employee_name: str) -> str:
        """Check leave balance for an employee."""
        if employee_name not in self.employees:
            return f"Employee {employee_name} not found."

        balance = self.employees[employee_name]
        return f"Current leave balance for {employee_name}:\n" + \
            "\n".join([f"- {leave_type}: {days} days" for leave_type, days in balance.items()])

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

    def cancel_leave(self, employee_name: str, leave_type: str, start_date: str) -> str:
        """Cancel a previously approved leave."""
        if employee_name not in self.leave_history:
            return f"No leave history found for {employee_name}"

        for leave in self.leave_history[employee_name]:
            if (leave["type"] == leave_type and
                    leave["start_date"] == start_date and
                    leave["status"] == "approved"):
                # Restore leave balance
                self.employees[employee_name][leave_type] += leave["days"]
                leave["status"] = "cancelled"

                # Save updated state
                self.save_state()

                return f"Leave cancelled successfully. {leave['days']} days of {leave_type} restored."

        return "No matching leave request found to cancel."

    def view_history(self, employee_name: str) -> str:
        """View leave history for an employee."""
        if employee_name not in self.leave_history:
            return f"No leave history found for {employee_name}"

        if not self.leave_history[employee_name]:
            return f"No leave records found for {employee_name}"

        history = f"Leave history for {employee_name}:\n"
        for record in self.leave_history[employee_name]:
            history += f"\n- {record['type']}: {record['days']} days from {record['start_date']} ({record['status']})"
        return history


def main():
    try:
        json_file_path = "employees.json"  # Path to your JSON file
        lms = LeaveManagementSystem(json_file_path)

        print("Welcome to the Leave Management System!")
        print("Please enter your name:")
        employee_name = input().strip()

        if employee_name not in lms.employees:
            print("Employee not found. Please try again.")
            return

        while True:
            print("\nWhat would you like to do? (Type 'exit' to quit)")
            user_input = input().strip()

            if user_input.lower() == 'exit':
                break

            # Process natural language input
            result = lms.process_natural_language(user_input, employee_name)

            if result.get("intent") == "check_balance":
                print(lms.check_leave_balance(employee_name))

            elif result.get("intent") == "request_leave":
                response = lms.request_leave(
                    employee_name,
                    result.get("leave_type"),
                    result.get("days"),
                    result.get("start_date")
                )
                print(response)

            elif result.get("intent") == "cancel_leave":
                response = lms.cancel_leave(
                    employee_name,
                    result.get("leave_type"),
                    result.get("start_date")
                )
                print(response)

            elif result.get("intent") == "view_history":
                print(lms.view_history(employee_name))

            elif result.get("intent") == "error":
                print(result.get("message", "Sorry, I couldn't understand that. Please try again."))

            else:
                print("I'm not sure what you want to do. Please try again.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")


if __name__ == "__main__":
    main()