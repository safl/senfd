# A small model, Llama 3.1 8B on 16 CPU cores, reads the question and picks the lookup
# It writes nothing of the answer: the answer is the model of the documents'
senfd-ask --llm http://127.0.0.1:8088 "hey, what opcode does migration send use?"
senfd-ask --llm http://127.0.0.1:8088 "where in CDW10 of sanitize do I set EMVS?"
senfd-ask --llm http://127.0.0.1:8088 "which FID is the rate limiting feature"
senfd-ask --llm http://127.0.0.1:8088 "is there a log page for rotational media, and what is its id?"
senfd-ask --llm http://127.0.0.1:8088 "the shutdown type bit in CSTS, where is it?"
# Asked what the documents do not say, it says so rather than make it up
senfd-ask --llm http://127.0.0.1:8088 "which bit of CDW12 of Write enables the hyperdrive?"
