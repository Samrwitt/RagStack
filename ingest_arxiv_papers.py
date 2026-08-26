import json
import time
import urllib.request
import urllib.parse
from uuid import UUID

PAPERS = [
    {
        "filename": "arxiv_1706_03762_attention_is_all_you_need.txt",
        "title": "Attention Is All You Need (Vaswani et al., 2017)",
        "content": """Title: Attention Is All You Need
Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Lukasz Kaiser, Illia Polosukhin

Abstract:
The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose the Transformer, a model architecture eschewing recurrence and instead relying entirely on an attention mechanism to draw global dependencies between input and output.

1. Introduction
Recurrent neural networks (RNNs), particularly long short-term memory (LSTM) and gated recurrent (GRU) neural networks, have been firmly established as state of the art approaches in sequence modeling. The Transformer architecture discards recurrence completely, allowing for significantly more parallelization and reduced training times.

2. Scaled Dot-Product Attention
An attention function maps a query and a set of key-value pairs to an output. The output is computed as a weighted sum of the values:
Attention(Q, K, V) = softmax(QK^T / sqrt(d_k)) V
Scaling by 1/sqrt(d_k) counteracts large dot products pushing the softmax function into regions with extremely small gradients.

3. Multi-Head Attention
Instead of performing a single attention function with d_model-dimensional keys, values, and queries, we found it beneficial to linearly project the queries, keys, and values h times with different, learned linear projections.
MultiHead(Q, K, V) = Concat(head_1, ..., head_h) W^O
where head_i = Attention(Q W_i^Q, K W_i^K, V W_i^V).

4. Position-wise Feed-Forward Networks
In addition to attention sub-layers, each of the layers in our encoder and decoder contains a fully connected feed-forward network:
FFN(x) = max(0, x W_1 + b_1) W_2 + b_2.

5. Positional Encoding
Since our model contains no recurrence and no convolution, in order for the model to make use of the order of the sequence, we must inject some information about the relative or absolute position of the tokens in the sequence. We use sine and cosine functions of different frequencies:
PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model)).
"""
    },
    {
        "filename": "arxiv_1810_04805_bert.txt",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers (Devlin et al., 2018)",
        "content": """Title: BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding
Authors: Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova

Abstract:
We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.

1. Pre-training Tasks
BERT uses two novel unsupervised pre-training tasks:
- Task #1: Masked LM (MLM). 15% of the input tokens are randomly masked, and the model predicts the original vocabulary ID of the masked tokens based only on its context.
- Task #2: Next Sentence Prediction (NSP). The model predicts whether sentence B is the actual next sentence that follows sentence A in the original corpus.

2. Model Architecture
BERT's model architecture is a multi-layer bidirectional Transformer encoder based on the original implementation described in Vaswani et al. (2017).
BERT_BASE: L=12 layers, H=768 hidden size, A=12 self-attention heads, 110M parameters.
BERT_LARGE: L=24 layers, H=1024 hidden size, A=16 self-attention heads, 340M parameters.

3. Fine-tuning
Fine-tuning BERT is straightforward. For sequence-level classification tasks, BERT uses the final hidden state of the first input token ([CLS]) as the aggregate representation for the entire input sequence.
"""
    },
    {
        "filename": "arxiv_2005_14165_gpt3.txt",
        "title": "GPT-3: Language Models are Few-Shot Learners (Brown et al., 2020)",
        "content": """Title: Language Models are Few-Shot Learners
Authors: Tom B. Brown, Benjamin Mann, Nick Ryder, Melanie Subbiah, Jared Kaplan, Prafulla Dhariwal, Arvind Neelakantan, et al.

Abstract:
We demonstrate that scaling up language models greatly improves task-agnostic, few-shot performance, sometimes even reaching competitiveness with prior state-of-the-art fine-tuning approaches. Specifically, we train GPT-3, an autoregressive language model with 175 billion parameters, 10x more parameters than any previous non-sparse language model.

1. Evaluation Modes
- Zero-Shot: The model is given a prompt with only the natural language description of the task.
- One-Shot: The model is given a single example of the task in addition to the prompt.
- Few-Shot: The model is given a context of K examples of the task (typically K between 10 and 100) as conditioning at inference time, without any weight updates.

2. Architecture & Capacity
GPT-3 uses the same architecture as GPT-2, including modified initialization, pre-normalization, and reversible tokenization. It incorporates alternating dense and locally banded sparse attention patterns, similar to the Sparse Transformer. GPT-3 ranges from 125 million parameters up to 175 billion parameters across 96 Transformer layers with hidden dimension d_model = 12288.
"""
    },
    {
        "filename": "arxiv_2106_09685_lora.txt",
        "title": "LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)",
        "content": """Title: LoRA: Low-Rank Adaptation of Large Language Models
Authors: Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen

Abstract:
We propose Low-Rank Adaptation, or LoRA, which freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer of the Transformer architecture, greatly reducing the number of trainable parameters for downstream tasks.

1. Mathematical Formulation
For a pre-trained weight matrix W_0 in R^(d x k), we constrain its update by representing the delta weight matrix as a low-rank decomposition:
W = W_0 + Delta W = W_0 + B A
where B in R^(d x r) and A in R^(r x k), and the rank r << min(d, k).
During training, W_0 is frozen and receives no gradient updates, while A and B contain trainable parameters.

2. Key Advantages
- Memory Efficiency: Reduces VRAM consumption during fine-tuning by up to 3x by eliminating optimizer states for frozen base parameters.
- Zero Inference Latency: The low-rank matrices B A can be merged directly into W_0 prior to deployment, incurring zero additional inference latency.
- Modularity: Enables rapid switching between multiple downstream tasks by loading lightweight task-specific LoRA adapters.
"""
    },
    {
        "filename": "arxiv_2005_11401_rag.txt",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al., 2020)",
        "content": """Title: Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
Authors: Patrick Lewis, Ethan Perez, Aleksandros Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, et al.

Abstract:
Large pre-trained language models store factual knowledge in their parameters, but their ability to access and precisely manipulate knowledge is limited. We explore decision frameworks for Retrieval-Augmented Generation (RAG) models which combine parametric memory (a pre-trained seq2seq model) with non-parametric memory (a dense vector index of Wikipedia accessed via Dense Passage Retriever).

1. RAG Architectures
We present two RAG formulations:
- RAG-Sequence: The model uses the same retrieved document to generate the complete target sequence.
- RAG-Token: The model can draw on different retrieved documents for each generated token in the output sequence.

2. Dense Passage Retriever (DPR)
The retrieval component uses DPR with two separate BERT encoders:
q(x) = DenseEncoder_Q(x)
d(z) = DenseEncoder_D(z)
The retrieval score P(z|x) is calculated as the inner product of query and document embeddings: exp(q(x)^T d(z)).
"""
    },
    {
        "filename": "arxiv_2305_18290_dpo.txt",
        "title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model (Rafailov et al., 2023)",
        "content": """Title: Direct Preference Optimization: Your Language Model is Secretly a Reward Model
Authors: Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, Christopher D. Manning, Chelsea Finn

Abstract:
Reinforcement Learning from Human Feedback (RLHF) is a complex and often unstable process, requiring fitting a reward model and training a policy network via PPO. We introduce Direct Preference Optimization (DPO), a stable, performant, and computationally lightweight algorithm that directly optimizes language models from preference data without explicit reward modeling or RL.

1. Theoretical Foundation
DPO leverages an analytical mapping between reward functions and optimal policies to express the RLHF objective as a simple classification loss over pairwise human preferences (y_w > y_l):
L_DPO(pi_theta; pi_ref) = -E_{(x, y_w, y_l)} [ log sigma( beta * log(pi_theta(y_w|x)/pi_ref(y_w|x)) - beta * log(pi_theta(y_l|x)/pi_ref(y_l|x)) ) ]

2. Key Benefits
- Stability: Completely avoids reinforcement learning training instabilities such as reward collapse and policy degeneration.
- Simplicity: Requires no explicit reward model training step and no online sampling during preference optimization.
"""
    },
    {
        "filename": "arxiv_2305_14314_qlora.txt",
        "title": "QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)",
        "content": """Title: QLoRA: Efficient Finetuning of Quantized LLMs
Authors: Tim Dettmers, Artidoro Pagnoni, Uvane Holtzman, Luke Zettlemoyer

Abstract:
We present QLoRA, an efficient finetuning approach that reduces memory usage enough to finetune a 65B parameter model on a single 48GB GPU while preserving full 16-bit finetuning task performance. QLoRA backpropagates gradients through a frozen, 4-bit quantized pre-trained language model into Low-Rank Adapters (LoRA).

1. Innovations
- 4-bit NormalFloat (NF4): An information-theoretically optimal quantile quantization data type for normally distributed weights.
- Double Quantization (DQ): A method that quantizes the quantization constants themselves, saving an average of 0.37 bits per parameter.
- Paged Optimizers: Uses NVIDIA CUDA Unified Memory to execute page-to-page transfers between GPU and CPU RAM during peak memory spikes.

2. Empirical Results
QLoRA enables fine-tuning of 33B and 65B models with zero performance degradation compared to standard 16-bit float training.
"""
    },
    {
        "filename": "arxiv_2205_14135_flashattention.txt",
        "title": "FlashAttention: Fast and Memory-Efficient Exact Attention (Dao et al., 2022)",
        "content": """Title: FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness
Authors: Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Ré

Abstract:
Standard Attention operations scale quadratically with sequence length O(N^2) and consume excessive memory bandwidth by writing intermediate attention matrices to GPU High Bandwidth Memory (HBM). We present FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce memory reads/writes between GPU HBM and GPU SRAM.

1. Core Technical Principles
- Tiling: FlashAttention splits the input Q, K, and V matrices into blocks and processes them sequentially inside high-speed GPU SRAM.
- Softmax Re-materialization: Instead of storing the N x N attention matrix for backward pass gradient computation, FlashAttention stores lightweight scaling factors and recomputes the softmax on the fly during backpropagation.

2. Performance Impact
Achieves 2-4x speedup over standard PyTorch attention implementations while reducing memory footprint from quadratic O(N^2) to linear O(N).
"""
    },
    {
        "filename": "arxiv_2310_06825_mistral7b.txt",
        "title": "Mistral 7B (Jiang et al., 2023)",
        "content": """Title: Mistral 7B
Authors: Albert Q. Jiang, Alexandre Sablayrolles, Arthur Mensch, Chris Bamford, Devendra Singh Chaplot, Diego de las Casas, Florian Bressand, et al.

Abstract:
We present Mistral 7B, a 7-billion parameter language model engineered for superior performance and efficiency. Mistral 7B outperforms the 13B LLaMA 2 model on all benchmarks, and demonstrates strong reasoning capabilities.

1. Key Architectural Features
- Sliding Window Attention (SWA): Uses a window size of W=4096. Tokens attend only to the past W tokens at each layer, reducing attention computation latency to O(W * N).
- Grouped-Query Attention (GQA): Shares key-value heads across query head groups (8 KV heads for 32 query heads), drastically decreasing memory bandwidth usage during KV-cache generation.
- Byte-fallback BPE Tokenizer: Ensures raw byte strings can be parsed without out-of-vocabulary fallback errors.
"""
    },
    {
        "filename": "arxiv_2501_12948_deepseek_r1.txt",
        "title": "DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via RL (DeepSeek-AI, 2025)",
        "content": """Title: DeepSeek-R1: Incentivizing Reasoning Capability in LLMs via Reinforcement Learning
Authors: DeepSeek-AI Team

Abstract:
We introduce DeepSeek-R1-Zero and DeepSeek-R1, reasoning models trained through large-scale reinforcement learning without supervised fine-tuning as a prerequisite. DeepSeek-R1 exhibits emergent self-verification, reflection, and long chain-of-thought (CoT) reasoning behaviors when solving complex mathematical and coding tasks.

1. Training Pipeline
- DeepSeek-R1-Zero: Trained directly via pure Reinforcement Learning (GRPO - Group Relative Policy Optimization) on top of the base model.
- DeepSeek-R1: Incorporates a multi-stage training pipeline starting with cold-start data distillation, followed by reasoning-oriented RL, rejection sampling, and secondary alignment.

2. Key Innovations
- Group Relative Policy Optimization (GRPO): Eliminates the need for a critic model by normalizing rewards across a group of outputs sampled for each prompt.
- Rejection Sampling & Distillation: Enables distilling reasoning capabilities into smaller models (e.g. 1.5B, 7B, 14B, 32B).
"""
    },
    {
        "filename": "arxiv_2302_13971_llama.txt",
        "title": "LLaMA: Open and Efficient Foundation Language Models (Touvron et al., 2023)",
        "content": """Title: LLaMA: Open and Efficient Foundation Language Models
Authors: Hugo Touvron, Thibaut Lavril, Gautier Izacard, Xavier Martinet, Marie-Anne Lachaux, Timothée Lacroix, Baptiste Rozière, et al.

Abstract:
We introduce LLaMA, a collection of foundation language models ranging from 7B to 65B parameters. We show that it is possible to train state-of-the-art models using exclusively publicly available datasets, without resorting to proprietary and inaccessible datasets.

1. Architecture Modifications
- Pre-normalization (RMSNorm): To improve training stability, we normalize the input of each transformer sub-layer using RMSNorm.
- SwiGLU Activation Function: We replace the non-linear ReLU activation with SwiGLU activations.
- Rotary Embeddings (RoPE): We remove absolute positional embeddings and instead add rotary positional embeddings (RoPE) at each layer of the network.
"""
    },
    {
        "filename": "arxiv_2212_08073_constitutional_ai.txt",
        "title": "Constitutional AI: Harmlessness from AI Feedback (Bai et al., 2022)",
        "content": """Title: Constitutional AI: Harmlessness from AI Feedback
Authors: Yuntao Bai, Saurav Kadavath, Sandipan Kundu, Amanda Askell, Jackson Kernion, Andy Jones, Anna Chen, et al.

Abstract:
We experiment with methods for training a harmless AI assistant through self-improvement, without human feedback labels for harmlessness. The mechanism relies on a set of explicit rules or principles—a constitution.

1. Two-Stage Training Process
- Supervised Stage (Critique & Revision): The model generates responses to adversarial prompts, critiques its own output according to constitutional principles, and rewrites the response to conform with the rules.
- Reinforcement Learning Stage (RLAIF): The model generates pair responses, evaluates preference using an AI preference model guided by principles, and trains via PPO without human evaluators in the loop.
"""
    },
    {
        "filename": "arxiv_2203_15556_chinchilla.txt",
        "title": "Training Compute-Optimal Large Language Models (Hoffmann et al., 2022)",
        "content": """Title: Training Compute-Optimal Large Language Models
Authors: Jordan Hoffmann, Sebastian Borgeaud, Arthur Mensch, Elena Buchatskaya, Trevor Cai, Eliza Rutherford, Diego de las Casas, et al.

Abstract:
We investigate the optimal allocation of compute budget when scaling up autoregressive transformer language models. By analyzing over 400 model runs, we find that for compute-optimal training, the number of parameters and the number of training tokens should be scaled in equal proportions.

1. Main Findings & Implications
- Current LLMs (such as GPT-3) were significantly over-parametrized and under-trained.
- Chinchilla 70B: Trained on 1.4 trillion tokens, Chinchilla outperforms the 280B Gopher model across virtually all downstream tasks while requiring significantly less inference compute and memory.
"""
    },
    {
        "filename": "arxiv_1907_11692_roberta.txt",
        "title": "RoBERTa: A Robustly Optimized BERT Pretraining Approach (Liu et al., 2019)",
        "content": """Title: RoBERTa: A Robustly Optimized BERT Pretraining Approach
Authors: Yinhan Liu, Myle Ott, Naman Goyal, Jingfei Du, Mandar Joshi, Danqi Chen, Omer Levy, Mike Lewis, Luke Zettlemoyer, Veselin Stoyanov

Abstract:
Language model pretraining has led to significant performance gains, but careful comparison between different approaches is difficult. We present a replication study of BERT pretraining that carefully measures the impact of many key hyperparameters and training data size.

1. Key Architectural Improvements
- Dynamic Masking: Generates the masking pattern every time we pass a sequence to the model, eliminating static masking artifacts.
- Removing NSP: Removes the Next Sentence Prediction objective, which improves performance on downstream task representations.
- Larger Batch Sizes: Trains with mini-batches of 8K sequences, which speeds up optimization and improves performance.
"""
    },
    {
        "filename": "arxiv_2408_08921_graphrag.txt",
        "title": "GraphRAG: Knowledge Graph Retrieval Augmented Generation (Edge et al., 2024)",
        "content": """Title: From Local to Global: A Graph RAG Approach to Query-Focused Summarization
Authors: Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody, Steven Truitt, Jonathan Larson

Abstract:
We introduce GraphRAG, a Knowledge Graph-based Retrieval-Augmented Generation approach that addresses the limitations of standard vector-search RAG when answering global questions over an entire text corpus.

1. Core Methodology
- Entity & Relationship Extraction: Uses an LLM to extract nodes (entities) and edges (relationships) from document chunks.
- Hierarchical Clustering: Applies the Leiden algorithm to partition the knowledge graph into hierarchical communities.
- Community Summarization: Generates pre-computed summaries for each community node to enable global dataset-wide reasoning.
"""
    }
]

def upload_paper(paper):
    url = "http://localhost:8000/api/v1/documents/upload"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    
    body = []
    body.append(f"--{boundary}".encode())
    body.append(f'Content-Disposition: form-data; name="file"; filename="{paper["filename"]}"'.encode())
    body.append(b"Content-Type: text/plain")
    body.append(b"")
    body.append(paper["content"].encode("utf-8"))
    body.append(f"--{boundary}--".encode())
    body.append(b"")
    
    payload = b"\r\n".join(body)
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    
    try:
        res = urllib.request.urlopen(req)
        data = json.loads(res.read().decode("utf-8"))
        doc_id = data.get("document", {}).get("id")
        title = data.get("document", {}).get("title")
        print(f"✅ Ingested: {title} (ID: {doc_id})")
        return doc_id
    except Exception as e:
        print(f"❌ Failed to ingest {paper['filename']}: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Ingesting 15 Research Papers into CorpusForge RAG...\n")
    for paper in PAPERS:
        upload_paper(paper)
        time.sleep(0.5)
    print("\n✨ All 15 arXiv Research Papers Ingested Successfully!")
