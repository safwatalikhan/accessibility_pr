# Accessibility Program Repair Benchmark

This repository contains the sampling, benchmark construction, and repair-generation infrastructure for evaluating automatic program repair on accessibility-related pull requests.

## Repository Components

* **`O1_sampling_algorithm.ipynb`**
  Samples **50 accessibility-related pull requests** from `master.csv` and writes the selected PRs to `sampled_prs.csv`.
  The sampling process is described in detail under **Pull Request Sampling Strategy**.

* **`O2_Create_Framework.py`**
  Clones/downloads the **buggy** and **fixed** versions of all **50 sampled PRs** and organizes them into application-level and issue-level subfolders.
  The benchmark organization is described in detail under **Benchmark Infrastructure**.

* **`O3_Script_prompt_engineering.py`**
  Uses prompt engineering with **Claude** and **OpenAI** models to generate accessibility repair patches for the sampled PRs.
  This process is described under **Automatic Program Repair**.

* **`O3_Script_agentic_ais.py`**
  Planned script for running **agentic AI-based repair workflows**.
  This component is currently **in progress**.

---

## Pull Request Sampling Strategy

From a manually curated dataset of **300 accessibility-related pull requests**, we selected a sample of **50 PRs** for detailed analysis and repair evaluation. This step is implemented in **`O1_sampling_algorithm.ipynb`**, which reads the full dataset from **`master.csv`** and outputs the sampled PRs to **`sampled_prs.csv`**.

Each PR in the dataset may be associated with multiple **issue types** and multiple affected **user demographics**, while each PR belongs to a single application. Because of this multi-label structure, simple random sampling is not suitable for our goal. A random sample could overrepresent frequent issue categories while missing less common but technically important accessibility problems. Therefore, we use a **coverage-based sampling strategy** that prioritizes coverage across issue types and user demographics while controlling the number of applications included in the final sample.

Our **primary sampling objective** is to maximize **issue type coverage** so that the sample captures a broad range of accessibility repair tasks. Different accessibility issue types often require different repair actions, such as adding missing labels, correcting focus behavior, improving keyboard navigation, or adjusting visual presentation. Prioritizing issue type coverage helps ensure that the selected PRs represent a wide range of repair scenarios rather than many examples of the same kind of accessibility fix.

Our **secondary objective** is to maximize **affected user demographic coverage**. Accessibility issues can affect different groups of users, including users with visual impairments, users with motor impairments, users with cognitive impairments, and users who rely on assistive technologies. Since this study evaluates accessibility program repair, it is important that the sampled PRs reflect different user demographics. Therefore, after issue type coverage, the sampling strategy prioritizes PRs that introduce previously uncovered user demographic labels.

Our **third objective** is to minimize the number of distinct applications required for evaluation while preserving issue type and user demographic coverage. This decision is motivated by the practical cost of conducting repair experiments on real-world applications. Each additional application requires separate setup effort, including cloning the project, installing dependencies, configuring the build environment, reproducing the issue, applying generated patches, and validating the repair. Since our primary goal is to evaluate accessibility repair behavior across issue categories rather than application-level variation, we treat the number of applications as an experimental cost. The sampling process also ensures that at least **10 applications** are selected.

The sampling algorithm processes each eligible PR and extracts three fields: the set of issue types, the set of affected user demographics, and the application name. Since issue type and user demographic fields are multi-label fields, comma-separated values are split and normalized by removing extra whitespace. PRs with missing issue type or user demographic annotations are excluded from the sampling process because they cannot reliably contribute to the coverage objectives.

During sampling, we maintain three sets representing the issue types, user demographics, and applications already included in the sample. For each candidate PR, the algorithm checks whether it introduces at least one previously uncovered issue type or user demographic. PRs that contribute new issue or user coverage are prioritized for selection. Application count is handled as a constraint: when multiple PRs provide similar issue and user coverage, the algorithm prefers PRs from applications already represented in the sample. This reduces the number of distinct applications needed for evaluation without sacrificing the main coverage goals.

After the coverage-driven selection step, if the sample contains fewer than **50 PRs**, the remaining slots are filled using additional eligible PRs from already selected applications whenever possible. This fill-up step ensures that the final sample reaches the target size of **50** while continuing to control the number of applications. If additional PRs from selected applications are insufficient, PRs from new applications are added only as needed to reach the target sample size.

Overall, this strategy produces a fixed-size sample that prioritizes coverage of accessibility issue types, maintains coverage of affected user demographics, and reduces the number of applications requiring experimental setup. This approach is appropriate for benchmark construction because the objective is not to estimate the population frequency of accessibility issues, but to create a manageable and well-covered set of real-world repair tasks for evaluating accessibility program repair.

---

## Benchmark Infrastructure

Following the sampling process, we construct a folder-based benchmark infrastructure to support repair evaluation on the selected PRs. This step is implemented in **`O2_Create_Framework.py`**, which processes the **50 sampled PRs**, retrieves their buggy and fixed versions, and organizes them into structured subfolders.

Since the sample contains multiple PRs from the same application, the infrastructure is organized first by application and then by issue. Each application is stored under an **`apps/`** directory using a folder name derived by concatenating the GitHub repository owner and repository name. Within each application folder, each sampled PR is stored as a separate issue directory named using its PR identifier. This structure allows multiple repair tasks from the same application to be grouped together while keeping each PR-level repair case separate.

For each sampled PR, the infrastructure script parses the GitHub PR link to identify the repository owner, repository name, and PR number. It then queries the GitHub API to retrieve PR metadata, including the PR title, database ID, merge status, merge commit SHA, and other PR-level information. These metadata are stored in an **`issue.json`** file inside each issue directory, making each repair case traceable to its original pull request.

Each issue directory contains separate folders for the buggy version, fixed version, generated repairs, prompts, reports, scripts, and environment files. To construct the **fixed** version, the script clones the repository, fetches the pull request branch using GitHub's **`pull/<PR_NUMBER>/head`** reference, and checks out the PR head. This represents the final developer-proposed or developer-merged repair state for the sampled PR.

To construct the **buggy** version, the script starts from the same PR head and then fetches the complete pull request diff from GitHub. It reverse-applies this diff using **`git apply -R`**, thereby removing the changes introduced by the PR and reconstructing the corresponding pre-fix version. This strategy handles both single-commit and multi-commit PRs consistently, because the buggy version is derived from the full PR-level diff rather than from the parent of a single commit.

After each buggy or fixed version is created, the script removes the **`.git`** directory from the checkout. This keeps the benchmark folders lightweight and avoids storing full Git history for every version. The resulting **`buggy/`** and **`fixed/`** folders contain only the source files needed for building, running, and validating the repair task.

The **`generated/`** directory stores repair outputs from different repair approaches. For the current prompt-engineering workflow, outputs are separated by model provider, such as **Claude** and **OpenAI**, so that generated patches can be stored and compared independently. The **`reports/`** directory stores build results and manual validation outcomes. Overall, this infrastructure preserves each sampled PR as a reproducible app-issue repair workspace while keeping the storage and setup cost manageable for the full benchmark.
---

## Automatic Program Repair

After constructing the benchmark infrastructure, we use automatic program repair techniques to generate candidate fixes for each sampled accessibility issue. This stage has two branches: **prompt-engineering-based repair** and **agentic AI-based repair**.

### Prompt-Engineering-Based Repair

The prompt-engineering workflow is implemented in **`O3_Script_prompt_engineering.py`**. This script prepares prompts for **Claude** and **OpenAI** models using information from each sampled PR and its buggy project version. The models are asked to generate candidate repair patches for the accessibility issue.

In this workflow, the repair models are given access only to the **buggy version** of the project and the issue-level information needed to understand the accessibility problem. The developer-fixed version is preserved separately for evaluation and comparison, but it is not exposed to the repair models during patch generation. This separation helps ensure that the generated patches reflect the model’s repair ability rather than direct access to the human-written fix.

The generated patches are stored under the corresponding issue directory so that outputs from different models can be reviewed, applied, built, and manually validated. This allows the benchmark to compare repair behavior across different Code LLMs while keeping each generated repair linked to its original PR, application, and issue metadata.

### Agentic AI-Based Repair

The second branch of the repair workflow will use **agentic AI systems** to perform accessibility program repair. This component is planned to be implemented in **`O3_Script_agentic_ais.py`**, which is currently **in progress**.

Unlike the prompt-engineering workflow, where a single prompt is used to request a patch, the agentic AI workflow will allow a repair agent to interact with the project more iteratively. For example, an agent may inspect files, identify relevant code locations, reason about the issue, propose a fix, and refine the patch based on intermediate results. This branch will be added to evaluate whether agentic repair workflows can produce more accurate or more complete accessibility fixes than direct prompt-engineering approaches.

Together, these two branches allow the benchmark to evaluate both direct Code LLM prompting and more autonomous agentic repair strategies for accessibility-related program repair.
