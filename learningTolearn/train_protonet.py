# -*- coding: utf-8 -*-
"""
   Description : 
   Author :        xxm
"""
import os
import sys

curPath = os.path.abspath(os.path.dirname(__file__))
rootPath = os.path.split(curPath)[0]
sys.path.append(rootPath)

import torch
from tqdm import tqdm

from torchmeta.utils.data import BatchMetaDataLoader

from learningTolearn.dataset import get_benchmark_by_name
from learningTolearn.method.metric import get_prototypes, get_accuracy, prototypical_loss
from learningTolearn.backbone import ModelConvOmniglot


def train(args):
    device = torch.device('cuda:0' if args.use_cuda and torch.cuda.is_available() else 'cpu')

    # 加载数据集
    benchmark = get_benchmark_by_name(args.dataset,
                                      args.folder,
                                      args.num_ways,
                                      args.num_shots,
                                      args.num_shots_test,
                                      hidden_size=args.hidden_size)
    # 训练集
    meta_train_dataloader = BatchMetaDataLoader(benchmark.meta_train_dataset,
                                                batch_size=args.batch_size,
                                                shuffle=True,
                                                num_workers=args.num_workers,
                                                pin_memory=True)
    # 验证集
    meta_val_dataloader = BatchMetaDataLoader(benchmark.meta_val_dataset,
                                              batch_size=args.batch_size,
                                              shuffle=True,
                                              num_workers=args.num_workers,
                                              pin_memory=True)

    model = ModelConvOmniglot(args.embedding_size, hidden_size=args.hidden_size, embedding=True)
    model.to(device=device)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    # Training loop
    with tqdm(meta_train_dataloader, total=args.num_batches) as pbar:
        for batch_idx, batch in enumerate(pbar):
            model.zero_grad()

            train_inputs, train_targets = batch['train']
            train_inputs = train_inputs.to(device=device)  # [16, 25, 1, 28, 28]
            train_targets = train_targets.to(device=device)  # [16, 25]
            train_embeddings = model(train_inputs)

            test_inputs, test_targets = batch['test']
            test_inputs = test_inputs.to(device=device)
            test_targets = test_targets.to(device=device)
            test_embeddings = model(test_inputs)

            prototypes = get_prototypes(train_embeddings, train_targets,
                                        benchmark.meta_train_dataset.num_classes_per_task)
            loss = prototypical_loss(prototypes, test_embeddings, test_targets)

            loss.backward()
            optimizer.step()

            with torch.no_grad():
                accuracy = get_accuracy(prototypes, test_embeddings, test_targets)
                pbar.set_postfix(accuracy='{0:.4f}'.format(accuracy.item()))

            if batch_idx >= args.num_batches:
                break

    # Save model
    if args.output_folder is not None:
        filename = os.path.join(args.output_folder,
                                'protonet_omniglot_{0}shot_{1}way.pt'.format(args.num_shots, args.num_ways))
        with open(filename, 'wb') as f:
            state_dict = model.state_dict()
            torch.save(state_dict, f)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser('Prototypical Networks')

    parser.add_argument('--folder', type=str, default='/Documents/Github/few-shot-datasets/',
                        help='Path to the folder the data is downloaded to.')
    parser.add_argument('--dataset', type=str,
                        choices=['sinusoid', 'omniglot', 'miniimagenet', 'tieredimagenet'], default='omniglot',
                        help='Name of the dataset (default: omniglot).')
    parser.add_argument('--num-shots', type=int, default=5,
                        help='Number of examples per class (k in "k-shot", default: 5).')
    parser.add_argument('--num-ways', type=int, default=5,
                        help='Number of classes per task (N in "N-way", default: 5).')
    parser.add_argument('--num-shots-test', type=int, default=15,
                        help='Number of test example per class. '
                             'If negative, same as the number of training examples `--num-shots` (default: 15).')

    parser.add_argument('--embedding-size', type=int, default=64,
                        help='Dimension of the embedding/latent space (default: 64).')
    parser.add_argument('--hidden-size', type=int, default=64,
                        help='Number of channels for each convolutional layer (default: 64).')

    parser.add_argument('--output-folder', type=str, default=None,
                        help='Path to the output folder for saving the model (optional).')
    parser.add_argument('--batch-size', type=int, default=16,
                        help='Number of tasks in a mini-batch of tasks (default: 16).')
    parser.add_argument('--num-batches', type=int, default=100,
                        help='Number of batches the prototypical network is trained over (default: 100).')
    parser.add_argument('--num-workers', type=int, default=1,
                        help='Number of workers for data loading (default: 1).')
    parser.add_argument('--download', action='store_true',
                        help='Download the Omniglot dataset in the data folder.')
    parser.add_argument('--use_cuda', action='store_true',
                        help='Use CUDA if available.')

    args = parser.parse_args()

    train(args)
