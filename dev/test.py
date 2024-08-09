import requests

data = {
    'user_id': "jiangziyou",
    'language': 'python',
    'code': 'def check_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True\n\n\nprime_sum = sum(i for i in range(101) if check_prime(i))\nprime_sum',
    'upload_file_name': None,
    'upload_file_url': None
}
response = requests.post(
    url='http://117.72.76.102:8090/run',
    json=data
)
print(response.json())