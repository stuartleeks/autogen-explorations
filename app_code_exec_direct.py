import asyncio
import os
import tempfile
from typing import Any, Optional

from anyio import open_file
from autogen_core import CancellationToken
from autogen_core.code_executor import CodeBlock
from autogen_ext.code_executors.azure import ACADynamicSessionsCodeExecutor
from azure.identity import DefaultAzureCredential
from azure.core.credentials import AccessToken

from auto_gen_explore import config

# https://microsoft.github.io/autogen/stable/user-guide/extensions-user-guide/azure-container-code-executor.html
# https://learn.microsoft.com/en-us/azure/container-apps/sessions-tutorial-autogen

cancellation_token = CancellationToken()
POOL_MANAGEMENT_ENDPOINT = config.aca_dynamic_sessions_pool_endpoint()


async def main1():
    with tempfile.TemporaryDirectory() as temp_dir:
        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )

        code_blocks = [
            CodeBlock(code="import sys; print('hello world!')", language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        assert code_result.exit_code == 0 and "hello world!" in code_result.output


async def main2():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file_1 = "test_upload_1.txt"
        test_file_1_contents = "test1 contents"
        test_file_2 = "test_upload_2.txt"
        test_file_2_contents = "test2 contents"

        # type: ignore[syntax]
        async with await open_file(os.path.join(temp_dir, test_file_1), "w") as f:
            await f.write(test_file_1_contents)
        # type: ignore[syntax]
        async with await open_file(os.path.join(temp_dir, test_file_2), "w") as f:
            await f.write(test_file_2_contents)

        assert os.path.isfile(os.path.join(temp_dir, test_file_1))
        assert os.path.isfile(os.path.join(temp_dir, test_file_2))

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )
        await executor.upload_files([test_file_1, test_file_2], cancellation_token)

        file_list = await executor.get_file_list(cancellation_token)
        assert test_file_1 in file_list
        assert test_file_2 in file_list

        code_blocks = [
            CodeBlock(
                code=f"""
with open("{test_file_1}") as f:
    print(f.read())
with open("{test_file_2}") as f:
    print(f.read())
    """,
                language="python",
            )
        ]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        assert code_result.exit_code == 0
        assert test_file_1_contents in code_result.output
        assert test_file_2_contents in code_result.output


async def main3():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file_1 = "test_upload_1.txt"
        test_file_1_contents = "test1 contents"
        test_file_2 = "test_upload_2.txt"
        test_file_2_contents = "test2 contents"

        assert not os.path.isfile(os.path.join(temp_dir, test_file_1))
        assert not os.path.isfile(os.path.join(temp_dir, test_file_2))

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )

        code_blocks = [
            CodeBlock(
                code=f"""
with open("{test_file_1}", "w") as f:
  f.write("{test_file_1_contents}")
with open("{test_file_2}", "w") as f:
  f.write("{test_file_2_contents}")
""",
                language="python",
            ),
        ]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        assert code_result.exit_code == 0
        print(f"Executed: {code_result}")

        file_list = await executor.get_file_list(cancellation_token)
        print(f"Files: {file_list}")
        assert test_file_1 in file_list
        assert test_file_2 in file_list

        await executor.download_files([test_file_1, test_file_2], cancellation_token)

        assert os.path.isfile(os.path.join(temp_dir, test_file_1))
        # type: ignore[syntax]
        async with await open_file(os.path.join(temp_dir, test_file_1), "r") as f:
            content = await f.read()
            assert test_file_1_contents in content
        assert os.path.isfile(os.path.join(temp_dir, test_file_2))
        # type: ignore[syntax]
        async with await open_file(os.path.join(temp_dir, test_file_2), "r") as f:
            content = await f.read()
            assert test_file_2_contents in content


async def main4():
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using work_dir: {temp_dir}")

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )

        code_blocks = [
            CodeBlock(code="""
import pkg_resources

# Get the list of installed packages
installed_packages = pkg_resources.working_set
packages_list = sorted(["%s==%s" % (pkg.key, pkg.version) for pkg in installed_packages])

# Save the list to a file named packages.txt
with open("packages.txt", "w") as f:
    f.write("\\n".join(packages_list))

""", language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        files = await executor.get_file_list(cancellation_token)
        print(f"Files: {files}")
        file_result = await executor.download_files(files, cancellation_token)
        print(f"Downloaded: {file_result}")
        for file in files:
            async with await open_file(os.path.join(temp_dir, file), "r") as f:
                content = await f.read()
                print(f"=============== {file} =======================\n{content}")
        input("Press Enter to continue...")

async def main5():
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using work_dir: {temp_dir}")

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )

        code_blocks = [
            CodeBlock(code="""
foo="bar"
""", language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        code_blocks = [
            CodeBlock(code="""
print(foo)
""", language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        input("Press Enter to continue...")


async def main6():
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using work_dir: {temp_dir}")

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )
        batches_path = os.path.join(os.path.dirname(__file__), "batches.csv")
        await executor.upload_files([batches_path], cancellation_token=cancellation_token)

        code_blocks = [
            CodeBlock(code='import pandas as pd\nimport matplotlib.pyplot as plt\n\n# Load the data from the file\nbatches_df = pd.read_csv(\'batches.csv\')\n\n# Create a dictionary to cache manufacturing times\nmanufacturing_time_cache = {}\n\n# Function to calculate the manufacturing time for a batch\ndef calculate_manufacturing_time(batch_id):\n    if batch_id in manufacturing_time_cache:\n        return manufacturing_time_cache[batch_id]\n    \n    batch = batches_df[batches_df[\'id\'] == batch_id].iloc[0]\n    source_batches = str(batch[\'source_batches\'])\n    \n    if pd.isna(source_batches) or source_batches.strip() == \'\':\n        total_time = batch[\'time\']\n    else:\n        source_batch_ids = [int(x) for x in source_batches.split(\',\') if x.strip().isdigit()]\n        total_time = batch[\'time\'] + sum(calculate_manufacturing_time(src_id) for src_id in source_batch_ids)\n    \n    manufacturing_time_cache[batch_id] = total_time\n    return total_time\n\n# Calculate manufacturing times for all batches\nbatches_df[\'total_time\'] = batches_df[\'id\'].apply(calculate_manufacturing_time)\n\n# Plot the batches by manufacturing time\nplt.figure(figsize=(10, 6))\nplt.bar(batches_df[\'id\'].astype(str), batches_df[\'total_time\'], color=\'skyblue\')\nplt.xlabel(\'Batch ID\')\nplt.ylabel(\'Manufacturing Time (Days)\')\nplt.title(\'Manufacturing Time for Each Batch\')\nplt.xticks(rotation=45)\nplt.tight_layout()\n\n# Save the plot to a file\nplt.savefig(\'batches_manufacturing_time.png\')\nprint("Plot saved as \'batches_manufacturing_time.png\'")\nprint(os.getcwd())\nprint(os.listdir(os.getcwd()))\n', language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        input("Press Enter to continue...")

async def main7():
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using work_dir: {temp_dir}")

        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )
        code_blocks = [
            CodeBlock(code='with open("output.txt" , "w") as f:\n\tf.write("hello world")\nprint(os.getcwd())\nprint(os.listdir(os.getcwd()))\n', language="python")]
        code_result = await executor.execute_code_blocks(code_blocks, cancellation_token)
        print(f"Executed: {code_result}")
        input("Press Enter to continue...")



# output current directory
# print(os.getcwd())
# list files in current directory
# print(os.listdir(os.getcwd()))


# asyncio.run(main1())
# asyncio.run(main2())
# asyncio.run(main3())
# asyncio.run(main4())
# asyncio.run(main5())
# asyncio.run(main6())
asyncio.run(main7())
