# Import necessary modules
import csv
from django.apps import apps
from datetime import datetime

Voucher = apps.get_model('voucher', 'Voucher')
# Define the path to your CSV file
csv_file_path = 'ecommerce/extensions/voucher/Vouchers-data.csv'

# Open the CSV file and read its contents
with open(csv_file_path, 'r') as file:
    reader = csv.DictReader(file)
    
    # Iterate through each row in the CSV file
    for row in reader:
        # Create a new instance of your Voucher model and populate its fields with data from the CSV
        voucher_instance = Voucher(
            name=row['name'],
            code=re.sub(r'[\W_]+', '',row['code']),
            usage=row['usage'],
            start_datetime=datetime.strptime(row['start_datetime'], '%Y-%m-%d %H:%M:%S'),
            end_datetime=datetime.strptime(row['end_datetime'], '%Y-%m-%d %H:%M:%S')
            # Add more fields as necessary
        )
        
        # Save the instance to the database
        voucher_instance.save()