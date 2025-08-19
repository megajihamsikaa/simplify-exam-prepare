string=input("enter a string")
processed_string=string.replace("","").lower()
if processed_string==processed_string[::-1]:
    print(f'{string} is a palindrome.')
else:
    print(f'{string}is not a palindrome.')
