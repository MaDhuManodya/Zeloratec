# from datetime import datetime
# import json
# from dotenv import load_dotenv
# import os
# from openai import OpenAI
#
# # Load environment variables from .env file
# load_dotenv()
#
#
# class LeaveManagementSystem:
#     # Update leave types to match the JSON structure
#     LEAVE_TYPES = [
#         "Sick Leave",
#         "Annual Leave",
#         "Maternity Leave"
#     ]
#
#     def __init__(self, json_file_path: str):
#         # Fetch API key from environment variable
#         api_key = os.getenv("OPENAI_API_KEY")
#         if not api_key:
#             raise ValueError("OPENAI_API_KEY environment variable is not set!")
#         self.client = OpenAI(api_key=api_key)
#
#         # Initialize json_file_path as instance variable
#         self.json_file_path = json_file_path
#
#         try:
#             # Load employee data from JSON file
#             with open(json_file_path, 'r') as file:
#                 self.employees = json.load(file)
#         except FileNotFoundError:
#             raise FileNotFoundError(f"Employee data file not found: {json_file_path}")
#         except json.JSONDecodeError:
#             raise ValueError(f"Invalid JSON format in file: {json_file_path}")
#
#         # Store leave history
#         self.leave_history = {name: [] for name in self.employees.keys()}
#
#     def process_natural_language(self, user_input: str, employee_name: str) -> dict:
#         """Process natural language input using OpenAI API."""
#         try:
#             response = self.client.chat.completions.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {
#                         "role": "system",
#                         "content": """
#                         You are a leave management assistant. Parse user queries for a system with exactly these leave types:
#                         - Sick Leave
#                         - Annual Leave
#                         - Maternity Leave
#
#                         Extract the following from user queries:
#                         1. For balance checks:
#                         - Intent: "check_balance"
#                         - Leave Type: one of the above types or "all" for all balances
#                         Example: {"intent": "check_balance", "leave_type": "Sick Leave"}
#
#                         2. For leave requests:
#                         - Intent: "request_leave"
#                         - Leave Type: one of the above types
#                         - Days: positive integer
#                         - Start Date: YYYY-MM-DD format
#                         Example: {"intent": "request_leave", "leave_type": "Annual Leave", "days": 3, "start_date": "2024-02-01"}
#
#                         3. For cancellations:
#                         - Intent: "cancel_leave"
#                         - Leave Type: one of the above types
#                         - Start Date: YYYY-MM-DD format
#
#                         4. For viewing history:
#                         - Intent: "view_history"
#
#                         Return JSON format only. For general balance inquiries use "all" as leave_type.
#                         Example user queries:
#                         - "How many sick leaves do I have?" -> {"intent": "check_balance", "leave_type": "Sick Leave"}
#                         - "Check my leave balance" -> {"intent": "check_balance", "leave_type": "all"}
#                         - "I want to take 3 days annual leave from next Monday" -> {"intent": "request_leave", "leave_type": "Annual Leave", "days": 3, "start_date": "2024-02-05"}
#                         """
#                     },
#                     {"role": "user", "content": user_input}
#                 ]
#             )
#
#             parsed_response = json.loads(response.choices[0].message.content)
#
#             # Validate leave type if present
#             if "leave_type" in parsed_response and parsed_response["leave_type"] != "all":
#                 if parsed_response["leave_type"] not in self.LEAVE_TYPES:
#                     return {
#                         "intent": "error",
#                         "message": f"Invalid leave type. Available types are: {', '.join(self.LEAVE_TYPES)}"
#                     }
#
#             # Validate required fields based on intent
#             if parsed_response.get("intent") == "request_leave":
#                 required_fields = ["leave_type", "days", "start_date"]
#                 missing_fields = [field for field in required_fields if field not in parsed_response]
#                 if missing_fields:
#                     return {
#                         "intent": "error",
#                         "message": f"Missing required information: {', '.join(missing_fields)}"
#                     }
#
#             return parsed_response
#
#         except Exception as e:
#             return {"intent": "error", "message": f"Error processing request: {str(e)}"}
#
#     def check_leave_balance(self, employee_name: str, leave_type: str = "all") -> str:
#         """Check leave balance for an employee."""
#         if employee_name not in self.employees:
#             return f"Employee {employee_name} not found."
#
#         balance = self.employees[employee_name]
#
#         if leave_type != "all":
#             if leave_type not in balance:
#                 return f"Invalid leave type: {leave_type}"
#             return f"Current {leave_type} balance for {employee_name}: {balance[leave_type]} days"
#
#         return f"Current leave balance for {employee_name}:\n" + \
#             "\n".join([f"- {leave_type}: {days} days" for leave_type, days in balance.items()])
#
#     def request_leave(self, employee_name: str, leave_type: str, days: int, start_date: str) -> str:
#         """Process a leave request."""
#         try:
#             # Validate date format
#             datetime.strptime(start_date, "%Y-%m-%d")
#         except ValueError:
#             return "Invalid date format. Please use YYYY-MM-DD format."
#
#         if employee_name not in self.employees:
#             return f"Employee {employee_name} not found."
#
#         if leave_type not in self.employees[employee_name]:
#             return f"Invalid leave type: {leave_type}"
#
#         if not isinstance(days, (int, float)) or days <= 0:
#             return "Number of days must be a positive number."
#
#         current_balance = self.employees[employee_name][leave_type]
#         if current_balance < days:
#             return f"Insufficient {leave_type} balance. You have {current_balance} days available."
#
#         # Process leave request
#         self.employees[employee_name][leave_type] -= days
#
#         # Record in history
#         leave_record = {
#             "type": leave_type,
#             "days": days,
#             "start_date": start_date,
#             "status": "approved",
#             "request_date": datetime.now().strftime("%Y-%m-%d")
#         }
#         self.leave_history[employee_name].append(leave_record)
#
#         # Save updated state
#         self.save_state()
#
#         return f"Leave request approved. {days} days of {leave_type} starting from {start_date}."
#
#     def save_state(self):
#         """Save the current state of employees back to the JSON file."""
#         try:
#             with open(self.json_file_path, 'w') as file:
#                 json.dump(self.employees, file, indent=4)
#         except Exception as e:
#             print(f"Error saving state: {str(e)}")
#
#
# def main():
#     try:
#         # Create a sample employees.json file if it doesn't exist
#         if not os.path.exists("employees.json"):
#             sample_data = {
#                 "Alice": {
#                     "Sick Leave": 5,
#                     "Annual Leave": 7,
#                     "Maternity Leave": 0
#                 },
#                 "Bob": {
#                     "Sick Leave": 8,
#                     "Annual Leave": 6,
#                     "Maternity Leave": 0
#                 },
#                 "Charlie": {
#                     "Sick Leave": 2,
#                     "Annual Leave": 12,
#                     "Maternity Leave": 0
#                 }
#             }
#             with open("employees.json", 'w') as file:
#                 json.dump(sample_data, file, indent=4)
#
#         lms = LeaveManagementSystem("employees.json")
#
#         print("Welcome to the Leave Management System!")
#         print("\nAvailable leave types:")
#         for leave_type in lms.LEAVE_TYPES:
#             print(f"- {leave_type}")
#
#         print("\nPlease enter your name:")
#         employee_name = input().strip()
#
#         if employee_name not in lms.employees:
#             print("Employee not found. Please try again.")
#             return
#
#         print(f"\nHello {employee_name}! Your current leave balance is:")
#         print(lms.check_leave_balance(employee_name))
#
#         while True:
#             print("\nWhat would you like to do? (Type 'exit' to quit)")
#             print("You can:")
#             print("- Check your leave balance")
#             print("- Request leave")
#             print("- View leave history")
#             print("- Cancel leave")
#
#             user_input = input().strip()
#
#             if user_input.lower() == 'exit':
#                 break
#
#             result = lms.process_natural_language(user_input, employee_name)
#
#             if result.get("intent") == "check_balance":
#                 leave_type = result.get("leave_type", "all")
#                 print(lms.check_leave_balance(employee_name, leave_type))
#
#             elif result.get("intent") == "request_leave":
#                 response = lms.request_leave(
#                     employee_name,
#                     result.get("leave_type"),
#                     result.get("days"),
#                     result.get("start_date")
#                 )
#                 print(response)
#
#             elif result.get("intent") == "view_history":
#                 print(lms.view_history(employee_name))
#
#             elif result.get("intent") == "error":
#                 print(result.get("message", "Sorry, I couldn't understand that. Please try again."))
#
#             else:
#                 print("I'm not sure what you want to do. Please try again.")
#
#     except Exception as e:
#         print(f"An error occurred: {str(e)}")
#
#
# if __name__ == "__main__":
#     main()