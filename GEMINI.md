# Gemini Code Assistant Context

This document outlines the project structure, conventions, and workflows for the `DupDetector` repository. It's designed to provide an AI assistant with the necessary context to effectively understand and contribute to the project.

## Project Overview

This repository contains a "spec-driven development" tool called `speckit`. It provides a structured workflow for defining, planning, and implementing new features. The core of the tool is a set of PowerShell scripts and templates that automate the process of creating feature specifications, implementation plans, and associated artifacts.

The workflow is centered around the concept of a "feature specification," which is a Markdown document that details the user stories, requirements, and success criteria for a new feature. The tool uses these specifications to generate implementation plans, which include technical context, data models, API contracts, and research tasks.

The tool is designed to be used with an AI assistant, and it includes functionality for updating the assistant's context with information about the technologies and conventions used in the project.

### Key Directories

*   `.specify/`: Contains the core logic and templates for the `speckit` tool.
    *   `scripts/powershell/`: PowerShell scripts that drive the workflow.
    *   `templates/`: Templates for feature specifications, implementation plans, and other artifacts.
    *   `memory/`: Long-term memory for the AI assistant, including the project's "constitution."
*   `.gemini/`: Contains configuration files for the Gemini AI assistant.
    *   `commands/`: Definitions for the `speckit` commands that can be executed by the assistant.
*   `specs/`: Directory where feature specifications and implementation plans are stored.

## Building and Running

The `speckit` tool is driven by PowerShell scripts. The primary entry point for creating a new feature is the `create-new-feature.ps1` script.

### Creating a New Feature

To create a new feature, run the following command from the repository root:

```powershell
.specify/scripts/powershell/create-new-feature.ps1 -ShortName <short-name> "<feature-description>"
```

This command will:

1.  Create a new Git branch for the feature.
2.  Create a new directory in the `specs/` directory for the feature.
3.  Create a new `spec.md` file in the feature directory, based on the `spec-template.md` template.
4.  Set the `SPECIFY_FEATURE` environment variable to the name of the feature branch.

### Planning a Feature

Once a feature specification has been created, the `speckit.plan` command can be used to generate an implementation plan. This command is designed to be executed by the Gemini AI assistant.

## Development Conventions

### Spec-Driven Development

This project follows a "spec-driven development" methodology. All new features must have a corresponding feature specification before implementation begins. The specification must include user stories, functional requirements, and success criteria.

### Implementation Planning

Once a feature specification has been approved, an implementation plan must be generated. The implementation plan must include a technical context, a data model, API contracts, and a research plan for any unknown or complex areas.

### AI Assistant Integration

The `speckit` tool is designed to be used with an AI assistant. The assistant is responsible for executing the `speckit` commands and for helping to generate the content of the feature specifications and implementation plans. The tool includes functionality for updating the assistant's context with information about the project.
