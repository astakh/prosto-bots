from openai import OpenAI
from config import DS_API_KEY, DS_API_URL
import json
import re

def clean_json_string(raw_string):
    if not isinstance(raw_string, str):
        return raw_string
    json_match = re.search(r'\{.*\}', raw_string, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
        cleaned = re.sub(r'[^\x20-\x7E\n\t]', '', cleaned)
        return cleaned
    return raw_string.strip()

async def query_model(messages):
    client = OpenAI(api_key=DS_API_KEY, base_url=DS_API_URL)

    # Добавляем инструкцию в конец сообщений, чтобы LLM вернула JSON
    messages_with_instruction = messages.copy() 

    not_first_trying = False
    for i in range(2):
        if not_first_trying:
            messages_with_instruction.append({'role': 'user', 'content': 'Верни ответ в формате JSON!'})
        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages_with_instruction,
                stream=False,
                response_format={ 'type': 'json_object' },
                temperature=1.4
            )
            raw_answer = response.choices[0].message.content 

            # Очищаем и парсим JSON
            cleaned_answer = raw_answer #  clean_json_string(raw_answer)
            answer_json = json.loads(cleaned_answer)    

            
            return answer_json

        except json.JSONDecodeError as e:
            print(f"Ошибка парсинга JSON: {e}, raw: {raw_answer}")
            not_first_trying = True
        except Exception as e:
            print(f"Ошибка при получении ответа: {e}")
            not_first_trying = True

    return {"response_to_user": "Извините, не удалось получить корректный ответ от модели."}