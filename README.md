<h1>CoAP</h1>

<h2>Features</h2>

1.	Web protocol fulfilling M2M requirements 
2.	UDP Binding
3.	Asynchronous message exchanges
4.	Low header overhead 
5.	Deduplication and package regrouping

<h2>Constrained Application Protocol</h2>
The interaction model of CoAP deals with interchanges asynchronously over UDP, but may also be used over Datagram Transport Layer Security (DTLS) or other transports. CoAP defines four types of messages: Confirmable, Non-confirmable, Acknowledgement, Reset.

<h2>Request/Response Model</h2>
CoAP request and response are carried in CoAP messages, which include either a Method Code or Response Code. Optional information are carried as CoAP options or/and Payload data, as specified by payload package format. A request is carried in a Confirmable (CON) or Non-confirmable (NON) message, and if immediately available, the response to a request carried in a CON message is piggybacked. If the server is not able to respond immediately to a request carried in a CON message, it responds with an Empty ACK message. When the response is ready, the server sends a separate response. If a request is sent in a NON message, then the response is sent using a new NON message. CoAP makes use of GET, PUT, POST, DELETE methods and the implemented JOMAG4 method. 

<h2>Message Format</h2>
CoAP messages are encoded in a simple binary format. The message format starts with a fixed-size 4-byte header. This is followed by a variable-length Token value, used to match an answer to a request. Following the Token value comes a sequence of zero or more CoAP Options in Type-Length-Value (TLV) format, optionally followed by the Payload Marker (0xFF) and the payload which extends to the end of the UDP datagram. The absence of the Payload Marker denotes a zero-length payload.
<br/><br/>

```
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |Ver| T |  TKL  |      Code     |          Message ID           |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    Token (if any, TKL bytes)		   |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                      Options (if any)  		           |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |1 1 1 1 1 1 1 1|      Payload (if any)  		           |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
                         Figure 1: Message Format
```
1. Version (Ver): 2-bit unsigned integer. Indicates the CoAP version number (01 binary). 
2. Type (T): 2-bit unsigned integer. Indicates if this message is of type CON (0), NON (1), ACK (2), or RST (3). 
3. Token Length (TKL): 4-bit unsigned integer. Indicates the length of the variable-length Token field (0-8 bytes). Lengths 9-15 are reserved. 
4. Code: 8-bit unsigned integer, split into a 3-bit class and a 5-bit detail as "c.dd" where "c" is 0 to 7 "dd" is from 00 to 31. 
5. Message ID: 16-bit unsigned integer in network byte order. 

Option Format
Each option instance in a message specifies the Option Number of the defined CoAP option, the length of the Option Value, and the Option Value itself. Instead of specifying the Option Number directly, the instances MUST appear in order of their Option Numbers and a delta encoding is used between them: the Option Number for each instance is calculated as the sum of its delta and the Option Number of the preceding instance in the message. 

```
   	  0   1   2   3   4   5   6   7
   	+---------------+---------------+
   	|  Option Delta | Option Length |   1 byte
   	+---------------+---------------+
   	|         Option Delta          |   0-2 bytes
   	|          (extended)           |
   	+-------------------------------+
   	|         Option Length         |   0-2 bytes
  	|          (extended)           |
  	+-------------------------------+
   	|         Option Value          |   0 or more bytes
   	+-------------------------------+
                  Figure 2: Option Format  
```
1. Option Delta: 4-bit unsigned integer. A value between 0 and 12 indicates the Option Delta. 13, 14, 15 are reserved.
2. Option Length: 4-bit unsigned integer. A value between 0 and 12 indicates the length of the Option Value, in bytes. 13, 14, 15 are reserved.
3. Value: A sequence of exactly Option Length bytes (int, string).

Message Transmission
As CoAP is bound to unreliable transports, messages may arrive out of order, appear duplicated, or go missing without notice. For this reason, CoAP implements a reliability mechanism that has the following features
1. Duplicate detection.
2. Package regroup for uploading.
3. Request drop in case of invalid or corrupted format.

Messages Transmitted Reliably
The reliable transmission of a message is initiated by marking the message as CON in the CoAP header. A recipient MUST either 
1. Acknowledge a CON message with an ACK message 
2. Reject the message if it can not process the message properly
Rejecting a CON message is effected by sending a matching RST message. The ACK message MUST carry a response or be Empty. The RST message MUST be Empty. 

Messages Transmitted without Reliability
A message can be transmitted less reliably by marking the message as NON. A NON message always MUST NOT be Empty or be acknowledged by the recipient. A recipient MUST reject the message if it lacks context to process the message properly by sending a matching RST message. 

```
                   +----------+-----+-----+-----+-----+
                   |          | CON | NON | ACK | RST |
                   +----------+-----+-----+-----+-----+
                   | Request  | X   | X   | -   | -   |
                   | Response | X   | X   | X   | -   |
                   | Empty    | *   | -   | X   | X   |
                   +----------+-----+-----+-----+-----+
                      Table 1: Usage of Message Types
"*" means that the combination is used to elicit a RST message ("CoAP ping").
```
<h2>Message Correlation</h2>
An ACK or RST message is related to a CON message or NON message by means of a Message ID along with additional address information of the corresponding endpoint.The Message ID is generated by the sender of a CON or NON message. The Message ID MUST be echoed in the ACK or RST message by the recipient.

<h2>Message Deduplication</h2>
A recipient might receive the same CON message multiple times and SHOULD acknowledge each duplicate of a CON message using the same ACK or RST message but SHOULD process it only once. A recipient might receive the same NON message multiple times and SHOULD silently ignore any duplicated NON message and SHOULD process it only once.
  
<h2>Options</h2>
CoAP defines a single set of options that are used in both requests and responses: Content-Format, Location-Path and Size1.

1.	The Content-Format Option indicates the format type of the message payload.
2.	The Location-Path indicates a path.
3.	Size1 indivates the total file size for uploading/downloading.

<h2>Payloads and Representations</h2>
Both requests and responses must include a payload because of the customized packages. The payload of requests or of responses indicating success is a binary representation of a resource or the result of the requested action. Its format is specified by the the Content-Format Option.

<h2>Payload format</h2>
<h4>1. FOR REQUESTS</h4>
	
* FILES

|ID	|OPCODE	|OPERATION	| MSG_TYPE		|ORD_NO_RULE	|OPER_PARAM		|	METHOD|
|---|-------|-----------|---------------|---------------|---------------|---------|
|1.	|	00	|   UPLOAD	|CONFIRMABLE	|>0 OR =0	|[CONTENT] OR NED|	PUT|
|2.	|	01	|   DOWNLOAD|FTC			|=0			|	NED			|	GET|
|3.	|	02	|   MOVE	|FTC			|= 0			|[NEW_FILEPATH]	|	POST|
|4.	|	03	|   DELETE	|FTC			|= 0			|	NED			|	DELETE|
|5.	|	04	|   RENAME	|FTC			|= 0			|[NEW_NAME]		|	JOMAG4|

* DIRECTORIES

|ID	|OPCODE	|OPERATION	|MSG_TYPE	|ORD_NO_RULE|	OPER_PARAM|	METHOD		|
| --  | --      |		---	|	----		|   ----  |  ------- |-------- |
|6.	|	05	|CREATE		|FTC		|= 0		|		NED	  |	PUT			|
|7.	|	06	|MOVE		|FTC		|= 0		|	[NEW_PATH]|		POST	|
|8.	|	07	|DELETE		|FTC		|= 0		|	NED	      |      DELETE	|
|9.	|	08	|RENAME		|FTC		|= 0		|	[NEW_NAME]|		JOMAG4	|

<h4>2. FOR RESPONSES</h4>

* FILES

|ID	|OPCODE|	OPERATION|	MSG_TYPE |ORD_NO_RULE | OPER_PARAM | METHOD |
|--|--|--|--|--|--|--|
|1.		|00	|UPLOAD		|NON|	=0			|NED				|	PUT  |
|2.		|01	|DOWNLOAD	|NON|	>0 OR =0	|[CONTENT] OR NED	|GET     |
|3.		|02	|MOVE		|NON|	 = 0		|NED				|	POST |
|4.		|03	|DELETE		|NON|	= 0			|NED				|	DELET|
|5.		|04	|RENAME		|NON|	= 0			|NED				|	JOMAG4|

* DIRECTORIES

|ID	|OPCODE|	OPERATION|	MSG_TYPE|	ORD_NO_RULE|	OPER_PARAM|	METHOD|
|--|--|--|--|--|--|--|
|6.		|05	|CREATE	|NON	|= 0	|NED	|PUT   |
|7.		|06	|MOVE	|NON	|= 0	|NED	|POST  |
|8.		|07	|DELETE	|NON	|= 0	|NED	|DELETE|
|9.		|08	|RENAME	|NON	|= 0	|NED	|JOMAG4|

1. DICTIONARY
<br>**FTC** = FREE TO CHOOSE.
<br>**MSG_TYPE** = MESSAGE TYPE.
<br>**ORD_NO_RULE** = ORDER NUMBER RULE.
<br>**OPER_PARAM** = OPERATION PARAMETERS.
<br>**NED** = NO EXTRA DATA WILL BE PRESENT IN PAYLOAD.
<br>**EOT** = END OF TRANSMISSION

3. DESCRIPTIONS
<br>**OPCODE** – PART OF PAYLOAD. SPECIFIES THE OPERATION CODE.
<br>**MSG_TYPE** – THE TYPE OF MESSAGE THROUGH WHICH THE REQUEST WAS SENT.
<br>**ORD_NO (DOWNLOAD/UPLOAD USE)** – PART OF PAYLOAD. IDENTIFIES IN ORDER PARTS OF THE SAME FILE (>0), OR MARKS THE EOT FOR THE FILE (=0)
<br>**ORD_NO_RULE** – THE ACCEPTED FORMAT FOR ORD_NO DETERMINED BY OPERATION.
<br>**OPER_PARAM** – PART OF PAYLOAD. OPERATION SPECIFIC PARAMETERS.
<br>**METHOD** – THE METHOD USED TO SENT THE REQUEST.

4. PACKAGE PARTs ORDER
<br>**OP_CODE** – 4 BITs
<br>**ORD_NO** – 2 BYTEs
<br>**OPER_PARAM CONTENT** – AS MUCH AS NEED FROM WHAT IS LEFT IN PAYLOAD SPACE
5. SIZEs
<br>ORD_NO SIZE IS 2 BYTEs (2^16-1 POSSIBLE VALUES).
<br>OP_CODE SIZE IS 4 BITs (15 POSSIBLE VALUES, 9 VALUES USED).

6. SERVER RESPONSE
<br>THE RESPONSE WILL CONTAIN THE SAME OPCODE AS THE REQUEST.
<br>ORD_NO WILL BE EQUAL TO 0, EXCEPT FOR DOWNLOAD OPERATION WHEN IT WILL KEEP THE PRESENTED MEANING (PART IDENTIFIER OR EOT MARKER).
<br>OPER_PARAM WILL BE NED FOR ALL OPERATIONS, EXCEPT FOR DOWNLOAD WHEN IT WILL CONTAIN THE REQUESTED CONTENT.

7. OTHERS
<br>AFTER TRANSMITTING THE MSG WITH THE LAST PART OF THE FILE, TO MARK THE EOT (FOR THAT FILE),  A NEW MSG WILL BE SENT WITH THE SAME TKN, THE SAME OPCODE, BUT THE ORD_NO EQUAL TO 0.
<br>JOMAG4 METHOD IS FOR RENAME OPERATION.
<br>THE PRESENTED REQUEST FORMAT IS MANDATORY.
<br>FAILURE IN APPLYING THE PAYLOAD FORMAT LEADS TO IGNORING THE REQUEST WITH RETURNING A RESPONSE CODE 4.00 - BAD REQUEST.



<h2>Method Definitions</h2>

1.	The GET method retrieves a representation for the information that currently corresponds to the resource identified by the request URI. Upon success, a 2.05 (Content) or 2.03 (Valid) Response Code should be present in the response.
2.	According to the POST method, the representation enclosed in the request must be processed. The actual function performed by the POST method is determined by the origin server and dependent on the target resource. It usually results in a new resource being created or the target resource being updated.
3.	The PUT method requests that the resource identified by the request URI be updated or created with the enclosed representation. The representation format is specified by the media type and content coding given in the Content-Format Option, if provided. 
4.	The DELETE method requests that the resource identified by the request URI be deleted.

<h2>Response Code Definitions</h2>
A response is identified by the Code field that indicates the result of the attempt to understand and satisfy the request.

<h3>Success 2.xx</h3>
<br>This class of Response Code indicates that the clients request was successfully received, understood, and accepted.
<br>2.01 Created - Used in response to PUT requests (upload and create functions).
<br>2.02 Deleted - Used in response to requests that cause the resource to cease being available (for delete function).
<br>2.04 Changed - Used in response to POST and JOMAG4 requests (remove and rename functions).
<br>2.05 Content - Used in response to GET requests. The payload returned with the response is a representation of the target resource (download function).

<h3>Client Error 4.xx</h3>
<br>This class of Response Code is intended for cases in which the client seems to have erred. These Response Codes are applicable to any request method. 
<br>4.00 Bad Request - The payload format was not applied as specified
<br>4.02 Bad Option - The request could not be understood by the server due to one or more unrecognized or malformed options. 
<br>4.04 Not Found

<h3>Server Error 5.xx</h3>
<br>This class of Response Code indicates cases in which the server is aware that it has erred or is incapable of performing the request. These Response Codes are applicable to any request method.
<br>5.00 Internal Server Error


<h2>Application Structure</h2>

![generic CoAP server](https://user-images.githubusercontent.com/74203905/211081934-a58c3f03-e772-403e-952b-97818c92fe06.png)

<h2>Bibliografie</h2>

1. RFC 7252: The Constrained Application Protocol (CoAP) - https://www.rfc-editor.org/rfc/rfc7252
2. Python documentation - https://docs.python.org/3/

