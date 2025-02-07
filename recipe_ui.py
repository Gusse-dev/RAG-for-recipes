import gradio as gr
from recipe_rag import RecipeRecommender


def chat_fn(query, history):
    history.append({'role': 'user', 'content': query})
    response = recipe_recommender.handle_query(query)
    history.append({'role': 'assistant', 'content': response['answer']})
    return "", history  

def clear_history():
    recipe_recommender.start_new_session()

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    title = gr.HTML("<h1>RecipeRecommender RAG</h1>")
    chatbot = gr.Chatbot(type='messages',height=700)
    user_input = gr.Textbox(placeholder="Type your message here...")
    clear_button = gr.Button("Clear Chat")

    user_input.submit(chat_fn, inputs=[user_input, chatbot], outputs=[user_input, chatbot])
    clear_button.click(clear_history, inputs=None, outputs=chatbot)

if __name__ == "__main__":
    recipe_recommender = RecipeRecommender('mistral','./recipe_vector_db','recipes')
    demo.launch()