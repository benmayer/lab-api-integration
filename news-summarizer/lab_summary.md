# Lab summary

I worked through the project section by section. One issue i faced was in retries: both SDKs retry on their own, which meant one failing Cohere call could have sent nine requests, so I turned the SDK retries off and kept a single retry loop in our code.

News API also returned two articles when I asked for three, which I could not fix, so the app now flags this when it happends instead of staying quiet. 

I learned to check what a library does by default before layering my own logic on top, and to write tests that I confirmed can fail by breaking the code on purpose. 

I also learnt about the risks of prompt injections when relying on articles or text published online. I added some counter measures to prevent obvious ones.

I used Claude Code to review and help me write the code step by step. I used my own Claude Code rather than Codex as i have my system already set up the way i like it for Claude Code. I reviewed and ran each step before moving on.