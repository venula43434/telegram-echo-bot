import os  # Add this at the beginning of the file to avoid 'os not defined' error
import telebot
import openai
import requests
from fpdf import FPDF
import pytz
from datetime import datetime
import traceback

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = '7797884542:AAEDZWHXPe3BVP-aJTVl0fiJRYjbqTs5-og'
GLHF_API_KEY = 'glhf_bdda99e9113d639d93affc202868580b'

# Configure OpenAI Client
try:
    client = openai.OpenAI(
        api_key=GLHF_API_KEY,
        base_url="https://glhf.chat/api/openai/v1"
    )
except Exception as e:
    print(f"OpenAI Client Initialization Error: {e}")
    client = None

# Initialize Telegram Bot
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

class UserContext:
    MAX_CONTEXT_LENGTH = 4000

    def __init__(self, mode='general'):
        self.messages = []
        self.mode = mode

    def add_message(self, role, content):
        self.messages.append({"role": role, "content": content})
        if len(self.messages) > self.MAX_CONTEXT_LENGTH:
            self.messages.pop(0)

    def clear_context(self):
        self.messages = []

class VirtualAssistantBot:
    def __init__(self):
        self.user_contexts = {}

    def get_ai_response(self, messages):
        if not client:
            return "Sorry, AI service is currently unavailable. Please try again later."

        try:
            if not isinstance(messages, list):
                return "Invalid message format."

            formatted_messages = [msg for msg in messages if isinstance(msg, dict) and 'role' in msg and 'content' in msg]

            if not formatted_messages:
                return "No valid messages to process."

            response = client.chat.completions.create(
                model="hf:nvidia/Llama-3.1-Nemotron-70B-Instruct-HF",
                messages=formatted_messages
            )

            if response.choices:
                return response.choices[0].message.content
            else:
                return "No response received from AI service."

        except requests.exceptions.RequestException as req_err:
            print(f"Network Error: {req_err}")
            return "Network error. Please check your internet connection."

        except Exception as e:
            print(f"Detailed Error: {traceback.format_exc()}")
            return f"Sorry, I'm experiencing technical difficulties. Please try again."

    def generate_lesson_pdf(self, lesson_content, title):
        try:
            pdf = FPDF()

            # Add title page with user question as the title
            pdf.add_page()
            pdf.set_font("Arial", size=20)
            pdf.cell(200, 20, txt=title, ln=True, align='C')
            pdf.ln(20)

            # Add lesson content (user question is removed from content)
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 10, lesson_content)

            # Add footer with copyright message
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.set_font("Arial", size=8)
            pdf.alias_nb_pages()
            pdf.footer = lambda: pdf.set_y(-15) or pdf.cell(0, 10, "© 2024 Plus Chatter - Founder: Venula Jayawardena", align="C")

            filename = f"{title.replace(' ', '_')}_lesson.pdf"

            counter = 1
            while os.path.exists(filename):
                filename = f"{title.replace(' ', '_Plus AI CHATBOT_')}_lesson_{counter}.pdf"
                counter += 1

            pdf.output(filename)
            return filename
        except Exception as e:
            print(f"PDF Generation Error: {e}")
            return None

    def setup_bot_handlers(self):
        @bot.message_handler(commands=['start'])
        def send_welcome(message):
            welcome_text = """
🤖 Welcome to AI Assistant Bot 🤖
• SELECT MODE YOU WANT TO GO IF AGAIN CHANGE TYPE /start •
/student_mode - Educational Assistance
/general_mode - General Knowledge Mode
/clear_chat - Clear Chat History
/datetime - Show Current Date and Time
/start - Again Open Menu
🤖 Founder Venula Jayawardena ☻ 🤖
            """
            bot.reply_to(message, welcome_text)
            self.initialize_user_context(message.chat.id)

        @bot.message_handler(commands=['student_mode'])
        def set_student_mode(message):
            self.user_contexts[message.chat.id] = UserContext(mode='student')
            bot.reply_to(message, "📚 Student Mode Activated! Ask me about any subject or lesson.")

        @bot.message_handler(commands=['general_mode'])
        def set_general_mode(message):
            self.user_contexts[message.chat.id] = UserContext(mode='general')
            bot.reply_to(message, "🌐 General Knowledge Mode Activated! Ask me anything.")

        @bot.message_handler(commands=['clear_chat'])
        def clear_chat_history(message):
            chat_id = message.chat.id
            if chat_id in self.user_contexts:
                self.user_contexts[chat_id].clear_context()
                bot.reply_to(message, "✨ Chat history has been cleared!")
            else:
                bot.reply_to(message, "No chat history to clear. ☺")

        @bot.message_handler(commands=['datetime'])
        def get_datetime(message):
            tz = pytz.timezone('UTC')
            current_time = datetime.now(tz)
            response = f"📅 Current Date and Time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            bot.reply_to(message, response)

        @bot.message_handler(func=lambda message: "lesson about" in message.text.lower())
        def handle_lesson_request(message):
            subject = message.text.lower().replace("lesson about", "").strip()
            if subject:
                bot.send_chat_action(message.chat.id, 'typing')
                lesson_content = self.get_ai_response([{
                    "role": "system", "content": "You are a helpful assistant. Please create a comprehensive and educational lesson about the given subject."
                }, {
                    "role": "user", "content": f"Create a detailed lesson about {subject}. Include examples and explanations for beginners and advanced learners."
                }])

                if "Sorry" not in lesson_content:
                    if len(lesson_content) > 4000:
                        for i in range(0, len(lesson_content), 4000):
                            bot.reply_to(message, lesson_content[i:i + 4000])
                    else:
                        bot.reply_to(message, lesson_content)

                    pdf_file = self.generate_lesson_pdf(lesson_content, f"Lesson on {subject.capitalize()}")
                    if pdf_file:
                        with open(pdf_file, 'rb') as file:
                            bot.send_document(message.chat.id, file)
                        os.remove(pdf_file)
                else:
                    bot.reply_to(message, "Sorry, I couldn't generate the lesson. Please try again later.")
            else:
                bot.reply_to(message, "Please specify the subject you want a lesson about.")

        @bot.message_handler(func=lambda message: True)
        def handle_message(message):
            try:
                chat_id = message.chat.id
                self.initialize_user_context(chat_id)

                bot.send_chat_action(chat_id, 'typing')

                user_context = self.user_contexts[chat_id]
                user_context.add_message("user", message.text)

                ai_messages = [{"role": m["role"], "content": m["content"]} for m in user_context.messages]

                response = self.get_ai_response(ai_messages)
                user_context.add_message("assistant", response)

                if len(response) > 4000:
                    for i in range(0, len(response), 4000):
                        bot.reply_to(message, response[i:i + 4000])
                else:
                    bot.reply_to(message, response)

                if user_context.mode == 'student':
                    pdf_file = self.generate_lesson_pdf(response, f"Detailed Answer for {message.text}")
                    if pdf_file:
                        with open(pdf_file, 'rb') as file:
                            bot.send_document(message.chat.id, file)
                        os.remove(pdf_file)

            except Exception as e:
                print(f"Message Handling Error: {traceback.format_exc()}")
                bot.reply_to(message, "Sorry, I encountered an error processing your message.")

    def initialize_user_context(self, chat_id):
        if chat_id not in self.user_contexts:
            self.user_contexts[chat_id] = UserContext()

    def start_bot(self):
        self.setup_bot_handlers()
        print("Bot is running...")
        bot.polling(none_stop=True)

def main():
    assistant_bot = VirtualAssistantBot()
    assistant_bot.start_bot()

if __name__ == "__main__":
    main()


