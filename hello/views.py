from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from dotenv import load_dotenv
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.files.storage import FileSystemStorage

from .models import Question

import pandas as pd
import openai
import numpy as np
import os

load_dotenv('.env')

openai.api_key = os.environ["OPENAI_API_KEY"]

COMPLETIONS_MODEL = "text-davinci-003"

MODEL_NAME = "curie"

DOC_EMBEDDINGS_MODEL = f"text-embedding-ada-002"
QUERY_EMBEDDINGS_MODEL = f"text-embedding-ada-002"

MAX_SECTION_LEN = 500
SEPARATOR = "\n* "
separator_len = 3

COMPLETIONS_API_PARAMS = {
    "temperature": 0.0,
    "max_tokens": 150,
    "model": COMPLETIONS_MODEL,
}

def get_embedding(text: str, model: str) -> list[float]:
    result = openai.Embedding.create(
      model=model,
      input=text
    )
    return result["data"][0]["embedding"]

def get_doc_embedding(text: str) -> list[float]:
    return get_embedding(text, DOC_EMBEDDINGS_MODEL)

def get_query_embedding(text: str) -> list[float]:
    return get_embedding(text, QUERY_EMBEDDINGS_MODEL)

def vector_similarity(x: list[float], y: list[float]) -> float:

    return np.dot(np.array(x), np.array(y))

def order_document_sections_by_query_similarity(query: str, contexts: dict[(str, str), np.array]) -> list[(float, (str, str))]:
    """
    Find the query embedding for the supplied query, and compare it against all of the pre-calculated document embeddings
    to find the most relevant sections.

    Return the list of document sections, sorted by relevance in descending order.
    """
    query_embedding = get_query_embedding(query)

    document_similarities = sorted([
        (vector_similarity(query_embedding, doc_embedding), doc_index) for doc_index, doc_embedding in contexts.items()
    ], reverse=True)

    return document_similarities

def load_embeddings(fname: str) -> dict[tuple[str, str], list[float]]:
    """
    Read the document embeddings and their keys from a CSV.

    fname is the path to a CSV with exactly these named columns:
        "title", "0", "1", ... up to the length of the embedding vectors.
    """

    df = pd.read_csv(fname, header=0)
    max_dim = max([int(c) for c in df.columns if c != "title"])
    return {
           (r.title): [r[str(i)] for i in range(max_dim + 1)] for _, r in df.iterrows()
    }

def construct_prompt(question: str, context_embeddings: dict, df: pd.DataFrame) -> tuple[str, str]:
    """
    Fetch relevant embeddings
    """
    most_relevant_document_sections = order_document_sections_by_query_similarity(question, context_embeddings)

    chosen_sections = []
    chosen_sections_len = 0
    chosen_sections_indexes = []

    for _, section_index in most_relevant_document_sections:
        document_section = df.loc[df['title'] == section_index].iloc[0]

        chosen_sections_len += document_section.tokens + separator_len
        if chosen_sections_len > MAX_SECTION_LEN:
            space_left = MAX_SECTION_LEN - chosen_sections_len - len(SEPARATOR)
            chosen_sections.append(SEPARATOR + document_section.content[:space_left])
            chosen_sections_indexes.append(str(section_index))
            break

        chosen_sections.append(SEPARATOR + document_section.content)
        chosen_sections_indexes.append(str(section_index))

    header = """"""

    question_1 = ""
    question_2 = ""
    question_3 = ""
    question_4 = ""
    question_5 = ""
    question_6 = ""
    question_7 = ""
    question_8 = ""
    question_9 = ""
    question_10 = ""

    return (header + "".join(chosen_sections) + question_1 + question_2 + question_3 + question_4 + question_5 + question_6 + question_7 + question_8 + question_9 + question_10 + "\n\n\nQ: " + question + "\n\nA: "), ("".join(chosen_sections))

def answer_query_with_context(
    query: str,
    df: pd.DataFrame,
    document_embeddings: dict[(str, str), np.array],
) -> tuple[str, str]:
    prompt, context = construct_prompt(
        query,
        document_embeddings,
        df
    )

    print("===\n", prompt)

    response = openai.Completion.create(
                prompt=prompt,
                **COMPLETIONS_API_PARAMS
            )

    return response["choices"][0]["text"].strip(" \n"), context

def index(request):
    return render(request, "index.html", { "default_question": "Ne sormak istersin?" })

@csrf_exempt
def ask(request):
    question_asked = request.POST.get("question", "")

    if not question_asked.endswith('?'):
        question_asked += '?'

    previous_question = Question.objects.filter(question=question_asked).first()

    if previous_question:
        print("previously asked and answered: " + previous_question.answer)
        previous_question.ask_count = previous_question.ask_count + 1
        previous_question.save()
        return JsonResponse({ "question": previous_question.question, "answer": previous_question.answer, "id": previous_question.pk })

    df = pd.read_csv('book.pdf.pages.csv')
    document_embeddings = load_embeddings('book.pdf.embeddings.csv')
    answer, context = answer_query_with_context(question_asked, df, document_embeddings)

    project_uuid = '6314e4df'
    voice_uuid = '0eb3a3f1'

    question = Question(question=question_asked, answer=answer, context=context)
    question.save()

    return JsonResponse({ "question": question.question, "answer": answer, "id": question.pk })

@login_required
def db(request):
    questions = Question.objects.all().order_by('-ask_count')

    return render(request, "db.html", { "questions": questions })

def question(request, id):
    question = Question.objects.get(pk=id)
    return render(request, "index.html", { "default_question": question.question, "answer": question.answer })

def upload_pdf(request):
    try:
        if request.method == 'POST' and request.FILES['pdf']:
            pdf_file = request.FILES['pdf']

            if pdf_file.content_type != 'application/pdf':
                return JsonResponse({'error': 'Invalid file type'}, status=400)

            fs = FileSystemStorage()
            file_name = 'book.pdf'
            file_path = os.path.join(settings.BASE_DIR, file_name)

            if fs.exists(file_path):  # Check if file exists
                fs.delete(file_path)  # If yes, delete the existing file

            file_name = fs.save(file_name, pdf_file)  # Save the new file

            return JsonResponse({'message': 'PDF uploaded successfully', 'file_name': file_name})
        
        return JsonResponse({'error': 'No PDF file provided'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)