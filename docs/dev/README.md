# Technical only

> The enforceable form of this intent is in `AGENTS.md`, section `docs/dev/` notes. This file is the author's rationale; update `AGENTS.md` when the rule changes.

This directory is organized to be reflected to `src/scripts` and `outputs`, so it is intuitive how you can match things together.

## Just Technical stuff

This directory is for technical and key implementation concepts that was used to program in `src/scropts`.
Unlike normal purpose of `docs/dev` where it highlights both the implementation details and guide to use each file, this directory is dedicated for technical and implementation concepts only.

## What to put

- It is not the details of the implementation. If they want the details, they read the code.
- It is about specific key technical concepts or specific key implementation in a script file and reasoning behind it.
- The report can be as technical as it can get.
- Give an example scenario on why this is logical.
- Should be short and concise, each word has weight. The goal is to make reader read then think, not spend time to read.
- identical is a rule with flexibility. You don't create this direcotry to be identical to `src/scripts` or `outputs` all the time, but most of the time you will find it is logical already to do it like that. But seeing there are other new directory means there are more dynamic to this directory than just simple matching.

## Some note on existing directory
- `software_concepts` is a space for exploring general concepts about software that will be used as blueprint for the implementation(before implementation).
- Other directories are almost identical. That is because they need to report based on the file they edit. This is after implementation.

- Note:  I never specify how to create file or what criteria the file should be created. This is open for agent to recommend and I select then update here.
