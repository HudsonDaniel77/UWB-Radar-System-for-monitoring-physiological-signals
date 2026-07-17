from docx import Document

# Load the document
doc = Document('Sleep_Detection_Project_Report.docx')

# Find and replace the title
for i, para in enumerate(doc.paragraphs):
    if 'Sleep Detection and Stage Classification System' in para.text and 'mmWave Radar' in para.text:
        # Replace with UWB-style title
        para.text = 'UWB Radar Based Sleep Monitoring System for Physiological Signal Analysis'
        print(f'Updated paragraph {i}: {para.text}')
        break

# Save the document
doc.save('Sleep_Detection_Project_Report.docx')
print('Project Report title updated successfully!')
