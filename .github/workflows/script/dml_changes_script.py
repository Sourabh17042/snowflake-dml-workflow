import os
import yaml
from collections import defaultdict
import snowflake.connector
import sys
import json
import re
from snowflake_connection_utility import get_private_key_from_env


def get_connection():
    """
    Establishes and returns a Snowflake database connection using environment variables.
    """
    user = os.getenv('SNOWFLAKE_USERNAME')
    account = os.getenv('SNOWFLAKE_ACCOUNT')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE', "SVC_ETL_XS_WAREHOUSE")
    role = os.getenv('SNOWFLAKE_ROLE')
    private_key = get_private_key_from_env()

    return snowflake.connector.connect(
            user=user,
            account=account,
            role=role,
            warehouse=warehouse,
            private_key=private_key,
        )


def execute_sql_function(folder, files):

    env = os.getenv('ENV_VARIABLE')

    # Execute each SQL command
    conn = get_connection()
    print(
        f"\nHello! Executing SQL function for folder '{folder}' with the following files:")
    cursor = conn.cursor()
    sql = f"Select FILENAME from {env}_SECURITY.SNF_MANAGEMENT.ADHOC_DML_CHANGELOG"
    sql_files = cursor.execute(sql)
    executed_sql_files = sql_files.fetchall()
    executed_sql_files = [row[0] for row in executed_sql_files]

    for i, sql_file in enumerate(files, 1):

        if sql_file.endswith(':changes.yml'):
            print(f"\tSkipping file: {sql_file} (Not an SQL file)")
            continue

        if sql_file.lower().endswith('.sql'):
            print(f"\t{i}. {sql_file}")

            if sql_file not in executed_sql_files:
                try:
                    with open(sql_file, 'r+') as file:
                        sql_content = file.readlines()
                        changeset_value = sql_content[:1]
                        remaining_sql_content = sql_content[1:]
                except Exception as e:
                    print(f"\tERROR: Unable to read file {sql_file}: {e}")
                    sys.exit(1)
                changeset_value = changeset_value[0]
                pattern = r'--changeset\s([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\:(.+)'
                match = re.search(pattern, changeset_value)

                insert_statement = None
                if match:
                    email = match.group(1)
                    file_id = match.group(2)
                    if service_now_number:
                        insert_statement = f'''INSERT INTO {env}_SECURITY.SNF_MANAGEMENT.ADHOC_DML_CHANGELOG
                                            (ID, AUTHOR, FILENAME, EXECTYPE, CR_NUMBER)
                                            VALUES ('{file_id}', '{email}', '{sql_file}','python', '{service_now_number}');'''
                    else:
                        insert_statement = f'''INSERT INTO {env}_SECURITY.SNF_MANAGEMENT.ADHOC_DML_CHANGELOG
                                            (ID, AUTHOR, FILENAME, EXECTYPE)
                                            VALUES ('{file_id}', '{email}', '{sql_file}','python');'''

                # Split the SQL content by semicolons and filter out commented lines
                sql_commands = []
                current_command = ""

                for line in remaining_sql_content:
                    stripped_line = line.strip()

                    # Skip comment lines and empty lines
                    if stripped_line.startswith('--') or not stripped_line:
                        continue

                    # Add the line to the current SQL command
                    current_command += " " + stripped_line

                    # If the line ends with a semicolon, it's the end of a SQL statement
                    if stripped_line.endswith(';'):
                        # Add the complete command to the list
                        sql_commands.append(current_command.strip())
                        current_command = ""  # Reset for the next command

                try:
                    with conn.cursor() as cursor:
                        for command in sql_commands:
                            cursor.execute(command)
                            print("\t\tSQL command executed successfully.")
                        if insert_statement:
                            cursor.execute(insert_statement)
                except Exception as e:
                    print(f"\t\tERROR: SQL execution failed: {e}")
                    sys.exit(1)
                finally:
                    conn.close()
        else:
            print(f"\tSkipping file: {sql_file} (Not an SQL file)")


def validate_changes_yml(changes_yml_path, file_list):

    print("\n\tProcess started for validating changes.yml file\n")
    files_in_changes_yml = []
    files_not_in_changes_yml = []

    try:
        with open(changes_yml_path, 'r') as file:
            changes_data = yaml.safe_load(file)

        # Extract file paths from changes.yml
        yml_files = [change['file_path']
                     for change in changes_data.get('changes', [])]

        # Check each file in the folder (except changes.yml) against changes.yml
        for file in file_list:
            if file.endswith("changes.yml"):
                continue
            # Remove the leading "./" from file paths to match with paths in changes.yml
            relative_path = file.lstrip("./")

            if relative_path in yml_files:
                files_in_changes_yml.append(relative_path)
            else:
                files_not_in_changes_yml.append(relative_path)

    except Exception as e:
        print(f"\t\tERROR: Unable to read or parse {changes_yml_path}: {e}")
        sys.exit(1)

    # Print the summary
    print("\n\tValidation Summary:\n")

    if files_in_changes_yml:
        print("\t\tFiles listed in changes.yml:")
        for i, file in enumerate(files_in_changes_yml, 1):
            print(f"\t\t\t{i}. {file}")
    else:
        print("\t\tNo files are listed in changes.yml.")

    if files_not_in_changes_yml:
        print("\n\tFiles NOT listed in changes.yml:")
        for i, file in enumerate(files_not_in_changes_yml, 1):
            print(f"\t\t\t{i}. {file}")
        return False
    else:
        print("\t\tAll files are listed in changes.yml.")
        return True


def process_added_files(added_files):
    if added_files:
        print(f"{added_files}")
        file_list = added_files.split()
        folder_files = defaultdict(list)

        all_folders_valid = True
        folder_files_for_sql = {}

        for file in file_list:
            folder_name = file.split('/')[1]
            folder_files[folder_name].append(file)

        for folder, files in folder_files.items():
            folder_files_for_sql[folder] = files
            execute_sql_function(folder, files)

        #     if folder != ".github":
        #         print(f"\n{folder} Folder Processing:")

        #         changes_yml_exists = any(file.endswith("changes.yml") for file in files)

        #         if changes_yml_exists:
        #             print(f"\tValid Folder '{folder}' because it contains: changes.yml")
        #             print(f"\t  Files added in '{folder}':")
        #             for i, file in enumerate(files, 1):
        #                 relative_path = file.lstrip("./")
        #                 print(f"\t\t{i}. {relative_path}")
        #             changes_yml_path = next(file for file in files if file.endswith("changes.yml"))
        #             if validate_changes_yml(changes_yml_path, files):
        #                 folder_files_for_sql[folder] = files
        #             else:
        #                 all_folders_valid = False
        #         else:
        #             print(f"\tInvalid Folder '{folder}' due to missing: changes.yml")
        #             for i, file in enumerate(files, 1):
        #                 relative_path = file.lstrip("./")
        #                 print(f"\t\t{i}. {relative_path}")
        #             all_folders_valid = False
        #     else:
        #         print(f"\n Skipping unsupported folder: '{folder}'. Only folders 'DEV', 'QA', or 'PROD' are processed.\n")

        # if all_folders_valid:
        #     # All folders have successfully validated their files against changes.yml
        #     for folder, files in folder_files_for_sql.items():
        #         execute_sql_function(folder, files)
        # else:
        #     print("All folder are not valid so not able to execute sql files")
        #     sys.exit(1)
    else:
        print("\nNo files were added or environment variable is not set.")


def main():
    added_files = os.getenv('ADDED_FILES')
    data_list = json.loads(added_files)

    result = ' '.join(f'./{item}' for item in data_list)

    process_added_files(result)


if __name__ == "__main__":
    env = os.getenv('ENV_VARIABLE')
    if env.lower() in ('dev', 'qa'):
        service_now_number = None
    else:
        service_now_number = sys.argv[1]
    main()