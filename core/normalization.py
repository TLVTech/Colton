import openai
import json

def complete_diagram_info(diagram_info, compliant_info):
    """
    Fills in diagram info fields based on the axle configuration and calls OpenAI for additional details.
    """
    config = compliant_info.get('OS - Axle Configuration', '')
    diagram_info = {}
    fields = []
    if config == '10 x 4':
        fields = ['F8','F7','R1','R2']
    if config == '10 x 6':
        fields = ['F8', 'F7', 'R1','R2','R3']
    if config == '10 x 8':
        fields = ['F8','F7', 'F6', 'R1', 'R2']
    if config == '4 x 2':
        fields = ['F8', 'R1']
    if config == '4 x 4':
        fields = ['F8', 'R1']
    if config == '6 x 2':
        fields = ['F8', 'R1']
    if config == '6 x 4':
        fields = ['F8', 'R1', 'R2']
    if config == '6 x 6':
        fields = ['F8', 'R1', 'R2']
    if config == '8 x 2':
        fields = ['F8', 'F7', 'R1']
    if config == '8 x 4':
        fields = ['F8', 'F7', 'R1', 'R2']
    if config == '8 x 6':
        fields = ['F8', 'R1', 'R2', 'R3']
    if config == '8 x 8':
        fields = ['F8', 'F7', 'R1', 'R2']

    # Pre-fill the main fields with blanks
    for field in fields:
        diagram_info[field+ ' Dual Tires'] = ''
        diagram_info[field+ ' Lift Axle'] = ''
        diagram_info[field+ ' Power Axle'] = ''
        diagram_info[field+ ' Steer Axle'] = ''

    myfields = ""
    diagram_info['R1 Dual Tires'] = 'yes'
    diagram_info['R1 Lift Axle'] = 'no'
    diagram_info['R1 Power Axle'] = 'yes'
    diagram_info['R1 Steer Axle'] = 'no'
    myfields += 'field name: "R1 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
    myfields += 'field name: "R1 Tire Size", meaning: "Tire Size". '
    myfields += 'field name: "R1 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum. '

    if 'R2 Dual Tires' in diagram_info:
        diagram_info['R2 Dual Tires'] = 'yes'
    if 'R2 Lift Axle' in diagram_info:
        diagram_info['R2 Lift Axle'] = 'no'
    if 'R2 Power Axle' in diagram_info:
        diagram_info['R2 Power Axle'] = 'yes'
    if 'R2 Steer Axle' in diagram_info:
        diagram_info['R2 Steer Axle'] = 'no'
        myfields += 'field name: "R2 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "R2 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "R2 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum. '

    if 'R3 Dual Tires' in diagram_info:
        diagram_info['R3 Dual Tires'] = 'no'
    if 'R3 Lift Axle' in diagram_info:
        diagram_info['R3 Lift Axle'] = 'yes'
    if 'R3 Power Axle' in diagram_info:
        diagram_info['R3 Power Axle'] = 'no'
    if 'R3 Steer Axle' in diagram_info:
        diagram_info['R3 Steer Axle'] = 'no'
        myfields += 'field name: "R3 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "R3 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "R3 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum. '

    if 'R4 Dual Tires' in diagram_info:
        diagram_info['R4 Dual Tires'] = 'no'
    if 'R4 Lift Axle' in diagram_info:
        diagram_info['R4 Lift Axle'] = 'yes'
    if 'R4 Power Axle' in diagram_info:
        diagram_info['R4 Power Axle'] = 'no'
    if 'R4 Steer Axle' in diagram_info:
        diagram_info['R4 Steer Axle'] = 'no'
        myfields += 'field name: "R4 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "R4 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "R4 Wheel Material", meaning: "Rear Wheel Type" either Steel or Aluminum. '

    diagram_info['F8 Dual Tires'] = 'no'
    diagram_info['F8 Lift Axle'] = 'no'
    diagram_info['F8 Power Axle'] = 'no'
    diagram_info['F8 Steer Axle'] = 'yes'
    myfields += 'field name: "F8 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
    myfields += 'field name: "F8 Tire Size", meaning: "Tire Size". '
    myfields += 'field name: "F8 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum. '

    if 'F7 Dual Tires' in diagram_info:
        diagram_info['F7 Dual Tires'] = 'no'
    if 'F7 Lift Axle' in diagram_info:
        diagram_info['F7 Lift Axle'] = 'no'
    if 'F7 Power Axle' in diagram_info:
        diagram_info['F7 Power Axle'] = 'no'
    if 'F7 Steer Axle' in diagram_info:
        diagram_info['F7 Steer Axle'] = 'yes'
        myfields += 'field name: "F7 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "F7 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "F7 Wheel Material", meaning: "Steer Wheel Type"  either Steel or Aluminum. '

    if 'F6 Dual Tires' in diagram_info:
        diagram_info['F6 Dual Tires'] = 'no'
    if 'F6 Lift Axle' in diagram_info:
        diagram_info['F6 Lift Axle'] = 'no'
    if 'F6 Power Axle' in diagram_info:
        diagram_info['F6 Power Axle'] = 'no'
    if 'F6 Steer Axle' in diagram_info:
        diagram_info['F6 Steer Axle'] = 'yes'
        myfields += 'field name: "F6 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "F6 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "F6 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum. '

    if 'F5 Dual Tires' in diagram_info:
        diagram_info['F5 Dual Tires'] = 'no'
    if 'F5 Lift Axle' in diagram_info:
        diagram_info['F5 Lift Axle'] = 'no'
    if 'F5 Power Axle' in diagram_info:
        diagram_info['F5 Power Axle'] = 'no'
    if 'F5 Steer Axle' in diagram_info:
        diagram_info['F5 Steer Axle'] = 'no'
        myfields += 'field name: "F5 Brake Type", meaning: "the type of brakes Disc or Drum or an empty string if not specified". '
        myfields += 'field name: "F5 Tire Size", meaning: "Tire Size". '
        myfields += 'field name: "F5 Wheel Material", meaning: "Steer Wheel Type" either Steel or Aluminum. '

    mytext = compliant_info.get('Original info description', '')
    mymessages = [
        {"role": "system", "content": f"You are a vehicle data extraction assistant. Extract information from the text and return it in a JSON format with these fields:{myfields}"},
        {"role": "user", "content": f"Extract vehicle information from this text: {mytext}"}
    ]
    print("mymessages")
    print(mymessages)
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=mymessages,
            temperature=0.1,
            max_tokens=1000
        )
        extracted_info = response.choices[0].message.content
        print("OpenAI debug output:")
        try:
            extracted_info = json.loads(extracted_info)
            extracted_info = {k: '' if v is None else v for k, v in extracted_info.items()}
            extracted_info.update(diagram_info)
            return extracted_info
        except json.JSONDecodeError:
            print("Warning: Response was not valid JSON")
            return None
    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return None
    return ''
