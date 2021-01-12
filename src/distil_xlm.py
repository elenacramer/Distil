from __future__ import unicode_literals, print_function

import numpy as np
import pandas as pd
import torch
from torch.utils.data import SequentialSampler, DataLoader
from tqdm import tqdm
from transformers import XLMForSequenceClassification, XLMTokenizer

from settings import distillation_settings, TRAIN_FILE, ROOT_DATA_PATH
from xlm_data import df_to_dataset
from xlm_trainer import batch_to_inputs
from lstm_trainer import LSTMDistilled
from utils import get_logger, device, set_seed


logger = get_logger()

set_seed(3)

# 1. get data and teacher model
train_df = pd.read_csv(TRAIN_FILE, encoding='utf-8', sep='\t')

xlm_model = XLMForSequenceClassification.from_pretrained('xlm-mlm-en-2048')
tokenizer = XLMTokenizer.from_pretrained('xlm-mlm-en-2048')

train_dataset = df_to_dataset(train_df, tokenizer, distillation_settings['max_seq_length'])
sampler = SequentialSampler(train_dataset)
data = DataLoader(train_dataset, sampler=sampler, batch_size=distillation_settings['train_batch_size'])

xlm_model.to(device())
xlm_model.eval()

xlm_logits = None

for batch in tqdm(data, desc="xlm logits"):
    batch = tuple(t.to(device()) for t in batch)
    inputs = batch_to_inputs(batch)

    with torch.no_grad():
        outputs = xlm_model(**inputs)
        _, logits = outputs[:2]

        logits = logits.cpu().numpy()
        if xlm_logits is None:
            xlm_logits = logits
        else:
            xlm_logits = np.vstack((xlm_logits, logits))

# 2.
X_train = train_df['sentence'].values
y_train = xlm_logits
y_real = train_df['label'].values

# 3. trainer
distiller = LSTMDistilled(distillation_settings, logger)

# 4. train
model, vocab = distiller.train(X_train, y_train, y_real, ROOT_DATA_PATH)