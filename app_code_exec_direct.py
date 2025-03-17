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



# asyncio.run(main1())
# asyncio.run(main2())
# asyncio.run(main3())
asyncio.run(main4())
# asyncio.run(main5())
