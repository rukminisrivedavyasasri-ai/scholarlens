import os
import fitz

PAPERS = [
    {
        "filename": "lora_paper.pdf",
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu",
        "pages": [
            (
                "LoRA: Low-Rank Adaptation of Large Language Models\n"
                "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Weizhu Chen\n\n"
                "Abstract\n"
                "An important paradigm of natural language processing consists of large-scale pre-training on general domain data "
                "and adaptation to specific tasks. As models grow, full fine-tuning becomes computationally prohibitive. "
                "We propose Low-Rank Adaptation, or LoRA, which freezes the pre-trained model weights and injects trainable rank decomposition "
                "matrices into each layer of the Transformer architecture, greatly reducing the number of trainable parameters for downstream tasks. "
                "LoRA reduces the number of trainable parameters by 10,000 times and GPU memory requirement by 3 times compared to GPT-3 175B fine-tuning. "
                "LoRA performs on-par or better than full fine-tuning on RoBERTa, DeBERTa, and GPT-3, while having higher throughput and no additional inference latency.\n\n"
                "1. Introduction\n"
                "Many applications rely on adapting one large, pre-trained language model to multiple downstream tasks. "
                "Full fine-tuning requires updating all parameters of the model. When deploying multiple adapted instances, "
                "storing multiple copies of multi-billion parameter models is prohibitively expensive. "
                "LoRA addresses this by decomposing parameter updates into low-rank matrices W = W_0 + B * A, where B in R^{d x r} and A in R^{r x k} with rank r << min(d, k)."
            ),
            (
                "2. Methodology and Parameter Efficiency\n"
                "In LoRA, during training W_0 is kept frozen and does not receive gradient updates. A Gaussian initialization is used for A "
                "and zero for B, so Delta W = B * A is zero at the beginning of training. We scale Delta W by alpha / r where alpha is a constant. "
                "When applied to GPT-3 175B, setting rank r = 4 results in only 37.7 million trainable parameters out of 175 billion (0.02% of parameters). "
                "Memory consumption during checkpointing drops from 350 GB to under 35 MB per task checkpoint.\n\n"
                "3. Empirical Findings on GLUE and SuperGLUE\n"
                "On the GLUE benchmark, LoRA matched or exceeded full fine-tuning accuracy across all tasks. "
                "Specifically, LoRA achieved 89.2% accuracy on MNLI and 92.4% on SST-2, matching full fine-tuning within 0.1% while requiring only 1/10,000th of the storage. "
                "4. Limitations\n"
                "A limitation of LoRA is that batching different tasks together in a single forward pass requires dynamically selecting weight branches, which introduces engineering complexity in high-throughput production servers."
            )
        ]
    },
    {
        "filename": "rag_paper.pdf",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "authors": "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni",
        "pages": [
            (
                "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks\n"
                "Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal\n\n"
                "Abstract\n"
                "Large pre-trained language models store factual knowledge in their parameters, but their ability to access and manipulate knowledge is limited, "
                "and they often hallucinate facts on knowledge-intensive tasks. We explore a general-purpose fine-tuning recipe for Retrieval-Augmented Generation (RAG). "
                "We build RAG models where the parametric memory is a pre-trained seq2seq model and the non-parametric memory is a dense vector index of Wikipedia, "
                "accessed with a pre-trained neural retriever (DPR). We compare two formulations: RAG-Sequence, which uses the same retrieved document across the whole sequence, "
                "and RAG-Token, which can select different documents per generated token. RAG models achieve state-of-the-art results on open-domain question answering benchmarks, "
                "generating more factual, specific, and diverse responses than parametric-only seq2seq baselines.\n\n"
                "1. Introduction\n"
                "Pre-trained neural models like BART and T5 cannot easily expand or revise their memory, can hallucinate, and cannot produce verifiable citations. "
                "Our hybrid RAG model couples parametric sequence generation with a non-parametric retriever accessing 21 million 100-word passages from Wikipedia."
            ),
            (
                "2. Architecture and Training\n"
                "The retriever uses Dense Passage Retrieval (DPR) with bi-encoder architectures. For a query x and passage z, the retrieval probability p(z|x) is proportional "
                "to exp(q(x)^T d(z)). The generator uses BART-large with 400M parameters. The model is trained end-to-end without direct supervision on which document to retrieve.\n\n"
                "3. Experimental Results\n"
                "On Natural Questions, RAG achieved 44.5 Exact Match (EM), outperforming the closed-book T5-11B baseline (34.5 EM) while using less than 10% of the parameters. "
                "On Jeopardy question generation, human evaluators rated RAG responses as 68% more factual than standard BART. "
                "4. Limitations\n"
                "RAG depends heavily on retriever recall; if the top-k passages do not contain the answer, the generator cannot recover the true entity."
            )
        ]
    },
    {
        "filename": "constitutional_ai.pdf",
        "title": "Constitutional AI: Harmlessness from AI Feedback",
        "authors": "Yuntao Bai, Saurav Kadavath, Sandipan Kundu, Amanda Askell",
        "pages": [
            (
                "Constitutional AI: Harmlessness from AI Feedback\n"
                "Yuntao Bai, Saurav Kadavath, Sandipan Kundu, Amanda Askell, Jackson Kernion, Andy Jones\n\n"
                "Abstract\n"
                "As AI systems become more capable, we would like to train them to be helpful and harmless without requiring extensive human feedback for harmful interactions. "
                "We propose Constitutional AI (CAI), a method for training a harmless AI assistant through self-improvement without human labels for harmfulness. "
                "The only human input is a list of principles or a constitution. The process involves two phases: supervised learning (SL) where the model critiques and revises its own responses, "
                "followed by reinforcement learning from AI feedback (RLAIF) where a preference model is trained on AI-generated critiques. "
                "Constitutional AI yields models that are harmless without sacrificing helpfulness, eliminating the need for human annotators to view disturbing content.\n\n"
                "1. Principles of the Constitution\n"
                "The constitution consists of roughly 60 principles derived from international declarations of human rights, trust and safety guidelines, and terms of service. "
                "During the critique phase, the model is prompted: 'Identify specific ways in which the assistant's response is harmful, toxic, or dangerous according to the principle.' "
                "The response is then rewritten until it complies with all specified constitutional criteria."
            ),
            (
                "2. Reinforcement Learning from AI Feedback (RLAIF)\n"
                "In the second phase, the model generates pairs of responses. An AI preference model judges which response is more harmless and helpful according to constitutional principles. "
                "We find that RLAIF achieves equivalent alignment quality to RLHF with human labelers, with a 0.73 correlation with expert human safety ratings.\n\n"
                "3. Findings\n"
                "Constitutional models exhibited 84% fewer harmful outputs on red-teaming benchmarks compared to standard RLHF models, "
                "while maintaining identical helpfulness scores on standard instruction-following evaluations. "
                "4. Limitations\n"
                "The method assumes the base model possesses sufficient meta-cognitive capability to critique its own completions accurately; smaller models under 10B parameters fail to execute constitutional critiques reliably."
            )
        ]
    },
    {
        "filename": "mamba_paper.pdf",
        "title": "Mamba: Linear-Time Sequence Modeling with Selective State Spaces",
        "authors": "Albert Gu, Tri Dao",
        "pages": [
            (
                "Mamba: Linear-Time Sequence Modeling with Selective State Spaces\n"
                "Albert Gu, Tri Dao\n\n"
                "Abstract\n"
                "Foundation models based on the Transformer architecture have achieved immense success, but suffer from computational inefficiency on long sequences due to quadratic attention complexity. "
                "Structured State Space Models (SSMs) offer linear-time scaling with sequence length, but struggle with content-based reasoning. "
                "We introduce Mamba, a selective state space architecture that makes SSM parameters input-dependent, allowing the model to selectively propagate or forget information along the sequence dimension. "
                "Mamba achieves linear-time training and inference complexity, processing sequences up to 1 million tokens efficiently on modern GPUs. "
                "Mamba-3B matches or exceeds Transformers of similar size across language modeling and downstream evaluations, while offering 5x higher inference throughput.\n\n"
                "1. Introduction\n"
                "Transformers require O(N^2) time and memory for sequence length N. Prior sub-quadratic alternatives like linear attention and traditional SSMs lacked selectivity—the ability to filter irrelevant context. "
                "Mamba integrates selection mechanisms directly into the continuous-time state space matrices (Delta, B, C) as a function of the input token."
            ),
            (
                "2. Hardware-Aware Hardware Algorithm\n"
                "To overcome memory bandwidth bottlenecks on GPUs, Mamba introduces a hardware-aware parallel scan that computes the recurrent state in SRAM rather than transferring intermediate states through HBM. "
                "This achieves a 3x speedup over standard scan implementations.\n\n"
                "3. Findings\n"
                "On the Pile benchmark, Mamba-2.8B achieved a perplexity of 5.89, outperforming Pythia-2.8B (perplexity 6.22) and LLaMA-3B equivalents. "
                "At sequence length 8192, Mamba achieved 5.2x faster inference generation than equivalent Transformer models. "
                "4. Limitations\n"
                "State space models exhibit lower in-context learning recall on needle-in-a-haystack tasks with more than 100 distracting entities compared to full softmax attention."
            )
        ]
    },
    {
        "filename": "flash_attention.pdf",
        "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
        "authors": "Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re",
        "pages": [
            (
                "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness\n"
                "Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re\n\n"
                "Abstract\n"
                "Transformers are slow and memory-intensive on long sequences, as the time and memory complexity of self-attention are quadratic in sequence length. "
                "Approximate attention methods trade off model quality to reduce compute, but rarely achieve wall-clock speedups due to memory access overhead. "
                "We propose FlashAttention, an IO-aware exact attention algorithm that uses tiling to reduce the number of memory reads/writes between GPU high bandwidth memory (HBM) and GPU on-chip SRAM. "
                "FlashAttention requires O(N^2) FLOPs like standard attention but reduces memory IO from quadratic to linear in sequence length, yielding 2-4x wall-clock speedups on A100 GPUs. "
                "FlashAttention enables training Transformers with longer context, improving perplexity and enabling 64K context windows.\n\n"
                "1. Introduction\n"
                "On modern GPUs, compute speed has outpaced memory bandwidth. Most operations in standard attention (softmax, dropout, masking) are memory-bound. "
                "Standard attention materializes intermediate N x N attention matrices in HBM, causing frequent IO bottlenecks."
            ),
            (
                "2. Tiling and Online Softmax\n"
                "FlashAttention splits inputs into blocks of size B_r and B_c that fit entirely within fast SRAM (192 KB per streaming multiprocessor on A100). "
                "Using the online softmax trick, FlashAttention computes scaling factors incrementally without ever storing the full N x N attention matrix to HBM. "
                "During the backward pass, attention matrices are recomputed on-the-fly from SRAM rather than cached in HBM, reducing memory footprint by 10-20x.\n\n"
                "3. Findings\n"
                "On GPT-2 training with 1K context length, FlashAttention yielded a 3.1x end-to-end training speedup over HuggingFace PyTorch implementations. "
                "On long-sequence benchmarks (sequence length 4K), FlashAttention achieved a 4.2x speedup and reduced peak memory consumption by 85%. "
                "4. Limitations\n"
                "FlashAttention requires custom CUDA kernel compilation and tailored block sizing for specific GPU microarchitectures (e.g. Ampere, Hopper)."
            )
        ]
    },
    {
        "filename": "clinical_nlp_paper.pdf",
        "title": "Clinical Triage and Diagnostic Accuracy of Medical Foundation Models",
        "authors": "Sarah Miller, David Chen, Rachel Adams, Marcus Thorne",
        "pages": [
            (
                "Clinical Triage and Diagnostic Accuracy of Medical Foundation Models\n"
                "Sarah Miller, David Chen, Rachel Adams, Marcus Thorne, Gregory House\n\n"
                "Abstract\n"
                "Evaluating large language models on medical triage is crucial before deployment in high-stakes healthcare environments. "
                "We present a multi-center evaluation of medical foundation models across 1,200 emergency department patient encounters. "
                "We evaluate three models: Med-PaLM 2, GPT-4, and specialized clinical fine-tunes on emergency triage acuity scoring (ESI levels 1-5). "
                "Medical foundation models achieved 88.4% diagnostic concordance with attending emergency physicians, "
                "significantly outperforming triage nurses on complex multi-morbid presentations. "
                "However, models demonstrated a 4.2% rate of critical omissions when assessing pediatric respiratory distress.\n\n"
                "1. Cohort and Data Collection\n"
                "The study enrolled 1,200 adult and pediatric emergency room presentations across three urban academic medical centers between 2023 and 2024. "
                "Cases were de-identified according to HIPAA Safe Harbor guidelines. Primary outcome measures included ESI acuity level alignment, "
                "differential diagnosis accuracy (top-3 recall), and safety hazard flag rates."
            ),
            (
                "2. Findings and Safety Analysis\n"
                "Across the full cohort, GPT-4 achieved 88.4% concordance with expert consensus panels. Med-PaLM 2 achieved 87.9%. "
                "Both models identified occult sepsis 42 minutes earlier than standard electronic health record (EHR) rule-based alerts on average. "
                "Triage acuity was correctly classified in 91.2% of high-acuity presentations (ESI 1 and 2).\n\n"
                "3. Limitations and Failure Modes\n"
                "A significant limitation identified was bias toward over-investigation in low-acuity presentations (ESI 4 and 5), "
                "where models recommended unnecessary CT scans in 14.8% of cases. The study did not evaluate non-English clinical encounters."
            )
        ]
    },
    {
        "filename": "synthetic_reasoning.pdf",
        "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        "authors": "Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Ed Chi, Quoc Le, Denny Zhou",
        "pages": [
            (
                "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models\n"
                "Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Ed Chi, Quoc Le, Denny Zhou\n\n"
                "Abstract\n"
                "We explore how generating a chain of thought—a series of intermediate reasoning steps—significantly improves the ability of large language models to perform complex reasoning. "
                "In particular, we show how such reasoning abilities emerge naturally in sufficiently large language models via a simple method called chain-of-thought prompting, "
                "where a few chain of thought demonstrations are provided as exemplars in few-shot prompting. "
                "Experiments on arithmetic, commonsense, and symbolic reasoning benchmarks show that chain-of-thought prompting dramatically outperforms standard prompting. "
                "On the GSM8K benchmark of math word problems, chain-of-thought prompting with PaLM 540B elevates solve accuracy from 17.9% to 58.1%, setting a new state of the art.\n\n"
                "1. Introduction\n"
                "Large models excel at intuitive translation and pattern matching, but fail on multi-step reasoning tasks like math word problems. "
                "Chain of thought mimics human deliberative problem-solving by breaking tasks down into structured intermediate thoughts: problem decomposition, deduction, and calculation."
            ),
            (
                "2. Benchmarks and Results\n"
                "We evaluated chain-of-thought prompting across GSM8K, SVAMP, and ASDiv arithmetic benchmarks, as well as CSQA and StrategyQA commonsense reasoning. "
                "On GSM8K, 8-shot chain-of-thought prompting achieved 58.1% accuracy with PaLM 540B, compared to 17.9% for standard 8-shot prompting. "
                "Chain-of-thought prompting exhibits an emergent ability: models with fewer than 100 billion parameters show zero or negligible benefit from chain-of-thought, "
                "whereas models larger than 100B parameters demonstrate dramatic leaps in performance.\n\n"
                "3. Limitations\n"
                "A major limitation is that chain of thought can produce plausible-sounding but factually unfaithful rationales where the model derives a correct answer through invalid mathematical reasoning."
            )
        ]
    }
]

def generate_papers(target_dir: str):
    os.makedirs(target_dir, exist_ok=True)
    for p in PAPERS:
        filepath = os.path.join(target_dir, p["filename"])
        doc = fitz.open()
        for page_text in p["pages"]:
            page = doc.new_page(width=595, height=842)
            rect = fitz.Rect(50, 50, 545, 792)
            page.insert_textbox(rect, page_text, fontsize=10, fontname="helv")
        doc.save(filepath)
        doc.close()
        print(f"Generated {p['filename']} ({len(p['pages'])} pages)")

if __name__ == "__main__":
    target = "c:/Users/RUKMINI/Downloads/25071A6958/capstone_/evaluation/benchmark_dataset"
    generate_papers(target)
