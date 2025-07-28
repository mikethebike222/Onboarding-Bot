import json
from openai import OpenAI
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatSession, ChatMessage, Vehicle
from datetime import datetime
import os
from dotenv import load_dotenv

# This manages communication with the client and openai until the connection is closed and all info is obtained
class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session = await self.create_chat_session()

        self.state = {
            "step": "zip",
            "zip": None,
            "name": None,
            "email": None,
            "vehicles": [],
            "license_type": None,
            "license_status": None,
            "current_vehicle": {}
            }
        
        self.chat = []
        load_dotenv()
        self.client = OpenAI(api_key = os.environ["OPENAI_API_KEY"])
        await self.accept()
        await self.send(text_data=json.dumps({"message": "Connection Established"}))

    @database_sync_to_async
    def create_chat_session(self):
        return ChatSession.objects.create()

    @database_sync_to_async
    def save_message(self, role, content):
        return ChatMessage.objects.create(
            session=self.session,
            role=role,
            content=content
        )

    # Update Session Db with collected data
    @database_sync_to_async
    def update_session_data(self):
        self.session.current_step = self.state["step"]
        self.session.zip_code = self.state.get("zip")
        self.session.full_name = self.state.get("name")
        self.session.email = self.state.get("email")
        self.session.license_type = self.state.get("license_type")
        self.session.license_status = self.state.get("license_status")
        
        # Check if we are complete based on the conditions
        if self.state["step"] == "license_type" and self.state.get("license_type") == "foreign":
            self.session.is_complete = True
            self.session.completed_at = datetime.now()
        elif self.state["step"] == "license_status" and self.state.get("license_status"):
            self.session.is_complete = True
            self.session.completed_at = datetime.now()
            
        self.session.save()

    # Save vehicle to Database
    @database_sync_to_async
    def save_vehicle(self, vehicle_data):
        print(vehicle_data)
        return Vehicle.objects.create(
            session=self.session,
            vin=vehicle_data["vin"],
            use_type=vehicle_data["use"],
            blind_spot=vehicle_data["blind_spot"],
            commute_days=vehicle_data.get("commute_days"), 
            commute_miles=vehicle_data.get("commute_miles"), 
            annual_mileage=vehicle_data.get("annual_mileage")
        )
    
    async def disconnect(self, close_code):
        print("Disconnected")

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_input = data["message"]
        await self.save_message("user", user_input)


        self.chat.append({"role": "user", "content": user_input})

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.make_msg(user_input)
        )

        text = response.choices[0].message.content.strip()

        parsed = json.loads(text)
        if parsed["valid"] and "zip" in parsed:
            self.state["zip"] = parsed["zip"]
            self.state["step"] = "name"

        elif parsed["valid"] and "name" in parsed:
            self.state["name"] = parsed["name"]
            self.state["step"] = "email"
        
        elif parsed["valid"] and "email" in parsed:
            self.state["email"] = parsed["email"]
            self.state["step"] = "add_vehicle"
        
        elif self.state["step"] == "add_vehicle" and parsed["valid"]:
            if "add_vehicle" in parsed and parsed["add_vehicle"]:
                self.state["step"] = "vehicle_vin"
            elif "no_vehicle" in parsed and parsed["no_vehicle"]:
                self.state["step"] = "license_type"

        elif self.state["step"] == "vehicle_vin" and parsed["valid"] and "vin" in parsed:
            self.state["current_vehicle"]["vin"] = parsed["vin"]
            self.state["step"] = "vehicle_use"

        elif self.state["step"] == "vehicle_use" and parsed["valid"] and "use" in parsed:
            self.state["current_vehicle"]["use"] = parsed["use"]
            self.state["step"] = "blind_spot"

        elif self.state["step"] == "blind_spot" and parsed["valid"] and "blind_spot" in parsed:
            self.state["current_vehicle"]["blind_spot"] = parsed["blind_spot"]

            if self.state["current_vehicle"]["use"] == "commuting":
                self.state["step"] = "commute_days"

            else:  
                self.state["step"] = "annual_mileage"

        elif self.state["step"] == "commute_days" and parsed["valid"] and "days" in parsed:
            self.state["current_vehicle"]["commute_days"] = parsed["days"]
            self.state["step"] = "commute_miles"

        elif self.state["step"] == "commute_miles" and parsed["valid"] and "miles" in parsed:
            self.state["current_vehicle"]["commute_miles"] = parsed["miles"]
            
            # Vehicle complete so save it
            await self.save_vehicle(self.state["current_vehicle"])

            self.state["vehicles"].append(self.state["current_vehicle"].copy())
            self.state["current_vehicle"] = {}
            self.state["step"] = "add_another_vehicle"

        elif self.state["step"] == "annual_mileage" and parsed["valid"] and "mileage" in parsed:
            self.state["current_vehicle"]["annual_mileage"] = parsed["mileage"]
            
            # Vehicle complete so save it
            await self.save_vehicle(self.state["current_vehicle"])

            self.state["vehicles"].append(self.state["current_vehicle"].copy())
            self.state["current_vehicle"] = {}
            self.state["step"] = "add_another_vehicle"

        elif self.state["step"] == "add_another_vehicle" and parsed["valid"]:
            if "add_vehicle" in parsed and parsed["add_vehicle"]:
                self.state["step"] = "vehicle_vin" 
            elif "no_vehicle" in parsed and parsed["no_vehicle"]:
                self.state["step"] = "license_type"  

        elif self.state["step"] == "license_type" and parsed["valid"] and "license_type" in parsed:
            self.state["license_type"] = parsed["license_type"]
            
            # If license is personal or commercial then ask for status
            if parsed["license_type"] in ["personal", "commercial"]:
                self.state["step"] = "license_status"
            else: 
                summary = f"""Information collected:
                    - ZIP: {self.state['zip']}
                    - Name: {self.state['name']}
                    - Email: {self.state['email']}
                    - Vehicles: {len(self.state['vehicles'])}
                    - License Type: {self.state['license_type']}
                    - License Status: {self.state.get('license_status', 'N/A')}"""
                await self.update_session_data()
                await self.save_message("assistant", summary)
                await self.send(text_data=json.dumps({"message": summary}))
                return

        elif self.state["step"] == "license_status" and parsed["valid"] and "license_status" in parsed:
            self.state["license_status"] = parsed["license_status"]
            summary = f"""Information collected:
                - ZIP: {self.state['zip']}
                - Name: {self.state['name']}
                - Email: {self.state['email']}
                - Vehicles: {len(self.state['vehicles'])}
                - License Type: {self.state['license_type']}
                - License Status: {self.state.get('license_status', 'N/A')}"""
            await self.save_message("assistant", summary)
            await self.send(text_data=json.dumps({"message": summary}))
            return
        
        await self.update_session_data()

        await self.save_message("assistant", parsed["message"])

        self.chat.append({"role": "assistant", "content": text})

        await self.send(text_data=json.dumps({"message": parsed["message"]}))


    # This method takes in the users input and looks at the current state we are in to prompt openai for an appropriate response.
    def make_msg(self, input):
        if self.state["step"] == "zip":
            return [
                {
                    "role": "system", 
                    "content": """You are a ZIP code validator. You MUST validate strictly.

        VALIDATION RULES:
        1. MUST be EXACTLY 5 digits - no more, no less
        2. MUST contain ONLY numbers (0-9)
        3. "1234" is INVALID (only 4 digits)
        4. "123456" is INVALID (6 digits)
        5. "12a45" is INVALID (contains letter)

        Count the digits carefully. If it's not exactly 5 digits, it's invalid.

        Response format (JSON only):
        {"message": "your message", "valid": true/false, "zip": "value only if valid"}

        Examples:
        - Input "1234" → {"message": "That's only 4 digits. Please enter a 5-digit ZIP code.", "valid": false}
        - Input "12345" → {"message": "Perfect! What's your full name?", "valid": true, "zip": "12345"}
        - Input "123456" → {"message": "That's 6 digits. ZIP codes need exactly 5 digits.", "valid": false}"""
                },
                {
                    "role": "user", 
                    "content": f"Validate this ZIP code: {input}"
                }
            ]
        elif self.state["step"] == "name":
            return [
                {
                    "role": "system",
                    "content": """You collect and validate full names for onboarding.

    VALIDATION RULES:
    1. Must include both first and last name
    2. Each name should be at least 2 characters
    3. Only letters, spaces, hyphens, and apostrophes allowed inside the name
    4. No numbers or special characters besides hyphen and apostrophe
    5. Names Can't have vulgar language in them

    Response format (JSON only):
    {"message": "your message", "valid": true/false, "name": "full name only if valid"}

    Examples:
    - Input "John" → {"message": "I need both your first and last name. Could you provide your full name?", "valid": false}
    - Input "John Smith" → {"message": "Thanks, John! Now I need your email address.", "valid": true, "name": "John Smith"}
    - Input "Mary-Jane O'Brien" → {"message": "Nice to meet you, Mary-Jane! What's your email address?", "valid": true, "name": "Mary-Jane O'Brien"}
    - Input "John123" → {"message": "Names shouldn't contain numbers. Please enter your full name using only letters.", "valid": false}"""
                },
                {
                    "role": "user",
                    "content": f"Validate this name: {input}"
                }
            ]
        elif self.state["step"] == "email":
            return [
                {
                    "role": "system",
                    "content": """You collect and validate email addresses for onboarding.

        VALIDATION RULES:
        1. Must have @ symbol
        2. Must have domain (e.g., .com, .org, .edu)
        3. Must have text before and after @
        4. No spaces allowed
        5. Standard email format: username@domain.extension

        Response format (JSON only):
        {"message": "your message", "valid": true/false, "email": "email only if valid"}

        Examples:
        - Input "john@gmail.com" → {"message": "Great! Now let's add your vehicle information. Do you want to add a vehicle?", "valid": true, "email": "john@gmail.com"}
        - Input "sarah.smith@company.org" → {"message": "Perfect! Ready to add vehicle details. Would you like to add a vehicle?", "valid": true, "email": "sarah.smith@company.org"}
        - Input "notanemail" → {"message": "That doesn't look like a valid email. Please include an @ symbol and domain.", "valid": false}
        - Input "john@" → {"message": "Your email seems incomplete. Please provide the full email address including the domain.", "valid": false}
        - Input "john smith@gmail.com" → {"message": "Email addresses can't contain spaces. Please enter a valid email.", "valid": false}"""
                },
                {
                    "role": "user",
                    "content": f"Validate this email: {input}"
                }
            ]
        elif self.state["step"] == "add_vehicle":
            return [
                {
                    "role": "system",
                    "content": """You ask if the user wants to add a vehicle and interpret their response.

        TASK: Determine if the user wants to add a vehicle or skip to license information.

        Interpret YES responses: "yes", "yeah", "sure", "ok", "y", "yep", "definitely", "I do", "let's do it", etc.
        Interpret NO responses: "no", "nope", "n", "not now", "skip", "no thanks", "later", "I don't", etc.

        Response format (JSON only):
        If they want to add a vehicle: {"message": "your message asking for VIN or Year/Make/Model/Body Type", "valid": true, "add_vehicle": true}
        If they don't want to add: {"message": "your message moving to license type question", "valid": true, "no_vehicle": true}
        If unclear: {"message": "your message asking for clarification", "valid": false}

        Examples:
        - Input "yes" → {"message": "Great! Please provide your vehicle's VIN or the Year, Make, Model, and Body Type.", "valid": true, "add_vehicle": true}
        - Input "no" → {"message": "No problem! Now I need to know your US License Type. Is it Foreign, Personal, or Commercial?", "valid": true, "no_vehicle": true}
        - Input "sure thing" → {"message": "Perfect! I'll need either your vehicle's VIN number or the Year, Make, Model, and Body Type.", "valid": true, "add_vehicle": true}
        - Input "maybe" → {"message": "I need a yes or no answer. Would you like to add a vehicle now?", "valid": false}"""
                },
                {
                    "role": "user",
                    "content": f"User response: {input}"
                }
            ]
        elif self.state["step"] == "vehicle_vin":
            return [
                {
                    "role": "system",
                    "content": """You collect vehicle identification information.

        Accept EITHER:
        1. A VIN (Vehicle Identification Number) - 17 characters
        2. Year, Make, Model, and Body Type (all four required)

        Response format (JSON only):
        {"message": "your message", "valid": true/false, "vin": "the VIN or year/make/model/body info"}

        Examples:
        - Input "1HGBH41JXMN109186" → {"message": "Got it! How is this vehicle primarily used? (commuting, commercial, farming, or business)", "valid": true, "vin": "1HGBH41JXMN109186"}
        - Input "2022 Honda Civic Sedan" → {"message": "Perfect! How do you primarily use this 2022 Honda Civic? (commuting, commercial, farming, or business)", "valid": true, "vin": "2022 Honda Civic Sedan"}
        - Input "Honda Civic" → {"message": "I need more details. Please provide either a VIN or the Year, Make, Model, and Body Type.", "valid": false}"""
                },
                {
                    "role": "user",
                    "content": f"Vehicle info: {input}"
                }
            ]

        elif self.state["step"] == "vehicle_use":
            return [
                {
                    "role": "system",
                    "content": """You collect vehicle use type.

        Valid uses: commuting, commercial, farming, business (accept variations)

        Response format (JSON only):
        {"message": "your message asking about blind spot warning", "valid": true/false, "use": "commuting/commercial/farming/business"}

        IMPORTANT: After validating the use type, immediately ask "Does this vehicle have blind spot warning equipped? (yes or no)"

        Examples:
        - Input "commuting" → {"message": "Does this vehicle have blind spot warning equipped? (yes or no)", "valid": true, "use": "commuting"}
        - Input "I use it for work" → {"message": "Is this for commuting to work or commercial/business use?", "valid": false}
        - Input "commercial" → {"message": "Got it, commercial use. Is this vehicle equipped with blind spot warning? (yes or no)", "valid": true, "use": "commercial"}
        - Input "farming" → {"message": "Got it, farming use. Does this vehicle have blind spot warning equipped? (yes or no)", "valid": true, "use": "farming"}
        - Input "business" → {"message": "Understood, business use. Is this vehicle equipped with blind spot warning? (yes or no)", "valid": true, "use": "business"}"""
                },
                {
                    "role": "user",
                    "content": f"Vehicle use: {input}"
                }
            ]

        elif self.state["step"] == "blind_spot":
            # Get the vehicle use type we already collected
            vehicle_use = self.state["current_vehicle"].get("use", "")
            
            if vehicle_use == "commuting":
                next_question = "How many days per week do you use this vehicle for commuting?"
            else:
                next_question = "What's the annual mileage for this vehicle?"
            
            return [
                {
                    "role": "system",
                    "content": f"""You ask about blind spot warning.

        Accept: yes/no variations (y, n, yeah, nope, etc.)

        Response format (JSON only):
        {{"message": "your message", "valid": true/false, "blind_spot": "yes/no"}}

        IMPORTANT: After validating the blind spot response, your message should ask: "{next_question}"

        Examples:
        - Input "yes" → {{"message": "Great to hear that your vehicle has blind spot warning. {next_question}", "valid": true, "blind_spot": "yes"}}
        - Input "no" → {{"message": "Noted, no blind spot warning. {next_question}", "valid": true, "blind_spot": "no"}}"""
                },
                {
                    "role": "user",
                    "content": f"Blind spot response: {input}"
                }
            ]

        elif self.state["step"] == "commute_days":
            return [
                {
                    "role": "system",
                    "content": """You collect days per week for commuting.

        Valid: 1-7 days

        Response format (JSON only):
        {"message": "your message asking for one-way miles", "valid": true/false, "days": number}

        Examples:
        - Input "5" → {"message": "And how many miles is your one-way commute to work or school?", "valid": true, "days": 5}
        - Input "every day" → {"message": "So that's 7 days a week. How many miles one-way to work/school?", "valid": true, "days": 7}"""
                },
                {
                    "role": "user",
                    "content": f"Days per week: {input}"
                }
            ]

        elif self.state["step"] == "commute_miles":
            return [
                {
                    "role": "system",
                    "content": """You collect one-way commute miles.


        Response format (JSON only):
        {"message": "your message about adding another vehicle", "valid": true/false, "miles": number}

        Examples:
        - Input "15" → {"message": "Great! Would you like to add another vehicle?", "valid": true, "miles": 15}
        - Input "10.5" → {"message": "Got it, 10.5 miles. Do you have another vehicle to add?", "valid": true, "miles": 10.5}"""
                },
                {
                    "role": "user",
                    "content": f"Miles: {input}"
                }
            ]

        elif self.state["step"] == "annual_mileage":
            return [
                {
                    "role": "system",
                    "content": """You collect annual mileage for commercial/farming/business vehicles.


        Response format (JSON only):
        {"message": "your message about adding another vehicle", "valid": true/false, "mileage": number}

        Examples:
        - Input "12000" → {"message": "Noted! Would you like to add another vehicle?", "valid": true, "mileage": 12000}
        - Input "15,000" → {"message": "Got it, 15,000 miles annually. Do you have another vehicle to add?", "valid": true, "mileage": 15000}"""
                },
                {
                    "role": "user",
                    "content": f"Annual mileage: {input}"
                }
            ]

        elif self.state["step"] == "add_another_vehicle":
            # Same as add_vehicle prompt but asking about another vehicle
            return [
                {
                    "role": "system",
                    "content": """Ask if they want to add another vehicle.

        Same logic as before - interpret yes/no responses.

        Response format (JSON only):
        If yes: {"message": "your message asking for next vehicle's VIN", "valid": true, "add_vehicle": true}
        If no: {"message": "your message about US license type which is either Foreign, Personal, or Commercial?", "valid": true, "no_vehicle": true}"""
                },
                {
                    "role": "user",
                    "content": f"Response: {input}"
                }
            ]
                
        elif self.state["step"] == "license_type":
            return [
                {
                    "role": "system",
                    "content": """You collect US License Type information.

        Valid types: Foreign, Personal, Commercial (accept case variations)

        Response format (JSON only):
        {"message": "your message", "valid": true/false, "license_type": "foreign/personal/commercial"}

        Examples:
        - Input "personal" → {"message": "Thank you. Is your personal license currently valid or suspended?", "valid": true, "license_type": "personal"}
        - Input "commercial" → {"message": "Got it, commercial license. Is it currently valid or suspended?", "valid": true, "license_type": "commercial"}
        - Input "foreign" → {"message": "Thank you! I've collected all your information. Here's a summary of what you provided...", "valid": true, "license_type": "foreign"}
        - Input "regular" → {"message": "Do you mean a personal license? Please specify: Foreign, Personal, or Commercial.", "valid": false}"""
                },
                {
                    "role": "user",
                    "content": f"License type: {input}"
                }
            ]

        elif self.state["step"] == "license_status":
            return [
                {
                    "role": "system",
                    "content": """You collect license status (only for personal or commercial licenses).

        Valid statuses: valid, suspended (accept variations like "active", "good standing" = valid)

        Response format (JSON only):
        {"message": "your message summarizing all collected information", "valid": true/false, "license_status": "valid/suspended"}

        Examples:
        - Input "expired" → {"message": "Is your license currently valid or suspended? Please specify one of these two options.", "valid": false}
        - Input "I don't know" → {"message": "I need to know if your license is valid or suspended. Please check and let me know.", "valid": false}
        - Input "revoked" → {"message": "I need to know if it's currently valid or suspended. If it's revoked, please indicate 'suspended'.", "valid": false}
        - Input "valid" → {"message": "Perfect! I've collected all your information. Here's what I have: [provide summary]", "valid": true, "license_status": "valid"}
        - Input "suspended" → {"message": "Noted. I've collected all your information. Here's a summary: [provide summary]", "valid": true, "license_status": "suspended"}
        - Input "active" → {"message": "Great, your license is active. Here's everything I've collected: [provide summary]", "valid": true, "license_status": "valid"}"""
                },
                {
                    "role": "user",
                    "content": f"License status: {input}"
                }
            ]

