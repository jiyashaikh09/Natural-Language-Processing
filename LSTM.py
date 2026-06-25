# ================================
# 📌 IMPORT LIBRARIES
# ================================
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# Keras / Deep Learning
from keras.preprocessing.text import Tokenizer
from keras_preprocessing.sequence import pad_sequences
from keras.models import Sequential
from keras.layers import Embedding, LSTM, Dense, RepeatVector
from keras.callbacks import ModelCheckpoint

# ML utilities
from sklearn.model_selection import train_test_split

# NLP
import spacy


# ================================
# 📌 DATA LOADING FUNCTIONS
# ================================

def read_text(filename):
    """
    Read a text file containing bilingual data.
    Each line contains a sentence pair.
    """
    with open(filename, mode='rt', encoding='utf-8') as file:
        text = file.read()
    return text


def to_lines(text, max_lines=None):
    """
    Split text into sentence pairs.
    Only first 2 columns are considered (English, German).
    """
    sents = text.strip().split('\n')
    sents = [i.split('\t')[:2] for i in sents]

    # Limit dataset (important for training performance)
    if max_lines:
        sents = sents[:max_lines]
    return sents


# ================================
# 📌 LOAD DATA
# ================================
data = read_text("Rawdata.txt")

# Convert into structured format
deu_eng = to_lines(data, max_lines=10000)
deu_eng = np.array(deu_eng)


# ================================
# 📌 PREPROCESSING (LOWERCASE)
# ================================
for i in range(len(deu_eng)):
    deu_eng[i, 0] = deu_eng[i, 0].lower()   # English
    deu_eng[i, 1] = deu_eng[i, 1].lower()   # German


# ================================
# 📌 TOKENIZATION
# ================================
def tokenization(lines):
    """
    Convert text into tokens (word index mapping).
    """
    tokenizer = Tokenizer()
    tokenizer.fit_on_texts(lines)
    return tokenizer


# Create tokenizers
eng_tokenizer = tokenization(deu_eng[:, 0])
deu_tokenizer = tokenization(deu_eng[:, 1])

# Vocabulary sizes
eng_vocab_size = len(eng_tokenizer.word_index) + 1
deu_vocab_size = len(deu_tokenizer.word_index) + 1

# Max sequence lengths
eng_length = max(len(line.split()) for line in deu_eng[:, 0])
deu_length = max(len(line.split()) for line in deu_eng[:, 1])


# ================================
# 📌 SEQUENCE ENCODING
# ================================
def encode_sequences(tokenizer, length, lines):
    """
    Convert sentences into padded sequences.
    """
    seq = tokenizer.texts_to_sequences(lines)
    seq = pad_sequences(seq, maxlen=length, padding='post')
    return seq


# ================================
# 📌 TRAIN-TEST SPLIT
# ================================
train, test = train_test_split(deu_eng, test_size=0.2, random_state=12)

# Input = German, Output = English
trainX = encode_sequences(deu_tokenizer, deu_length, train[:, 1])
trainY = encode_sequences(eng_tokenizer, eng_length, train[:, 0])

testX = encode_sequences(deu_tokenizer, deu_length, test[:, 1])
testY = encode_sequences(eng_tokenizer, eng_length, test[:, 0])


# ================================
# 📌 MODEL BUILDING (LSTM)
# ================================
def build_model(in_vocab, out_vocab, in_timesteps, out_timesteps, units):
    """
    Build encoder-decoder LSTM model.
    """
    model = Sequential()

    # Encoder
    model.add(Embedding(in_vocab, units, input_length=in_timesteps, mask_zero=True))
    model.add(LSTM(units))

    # Decoder
    model.add(RepeatVector(out_timesteps))
    model.add(LSTM(units, return_sequences=True))

    # Output layer
    model.add(Dense(out_vocab, activation='softmax'))

    return model


# Create model
model = build_model(deu_vocab_size, eng_vocab_size, deu_length, eng_length, 512)

# Compile model
model.compile(
    optimizer='rmsprop',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)


# ================================
# 📌 MODEL TRAINING
# ================================
checkpoint = ModelCheckpoint(
    'best_model.keras',
    monitor='val_loss',
    save_best_only=True,
    verbose=1
)

history = model.fit(
    trainX,
    trainY.reshape(trainY.shape[0], trainY.shape[1], 1),
    epochs=100,
    batch_size=512,
    validation_split=0.2,
    callbacks=[checkpoint],
    verbose=1
)


# ================================
# 📌 POS TAGGING + NER USING SPACY
# ================================

# Load models
nlp_eng = spacy.load('en_core_web_sm')
nlp_ger = spacy.load('de_core_news_sm')

def pos_ner_spacy(sentences, nlp):
    """
    Perform POS tagging and Named Entity Recognition.
    """
    pos_tags = []
    entities = []

    for sent in sentences:
        doc = nlp(str(sent))

        pos_tags.append([(token.text, token.pos_) for token in doc])
        entities.append([(ent.text, ent.label_) for ent in doc.ents])

    return pos_tags, entities


# Example extraction
eng_sentences = deu_eng[:, 0]
ger_sentences = deu_eng[:, 1]

eng_pos_tags, eng_entities = pos_ner_spacy(eng_sentences, nlp_eng)
ger_pos_tags, ger_entities = pos_ner_spacy(ger_sentences, nlp_ger)


# ================================
# 📌 REVERSE DICTIONARY
# ================================
eng_index_word = {index: word for word, index in eng_tokenizer.word_index.items()}
deu_index_word = {index: word for word, index in deu_tokenizer.word_index.items()}


# ================================
# 📌 PREDICTION FUNCTION
# ================================
from keras.models import load_model

def predict_sequence(model, tokenizer, source_seq, index_word, max_length):
    """
    Generate translated sentence from input sequence.
    """
    predicted_sequence = []

    # Add special tokens if missing
    for token in ['<start>', '<end>', '<unk>']:
        if token not in tokenizer.word_index:
            tokenizer.word_index[token] = len(tokenizer.word_index) + 1

    # Initialize decoder
    target_seq = np.zeros((1, 1))
    target_seq[0, 0] = tokenizer.word_index['<start>']

    for i in range(max_length):
        output = model.predict([source_seq, target_seq], verbose=0)

        predicted_index = np.argmax(output[0, i, :])
        predicted_word = index_word.get(predicted_index, '<unk>')

        if predicted_word == '<end>':
            break

        predicted_sequence.append(predicted_word)

        target_seq[0, 0] = predicted_index

    return ' '.join(predicted_sequence)


# ================================
# 📌 LOAD MODEL + TEST PREDICTION
# ================================
model = load_model('best_model.keras')

input_sequence = "entschuldigung"

source_seq = encode_sequences(deu_tokenizer, deu_length, [input_sequence])

predicted_sentence = predict_sequence(
    model,
    eng_tokenizer,
    source_seq,
    eng_index_word,
    eng_length
)

print("Input:", input_sequence)
print("Predicted Translation:", predicted_sentence)
