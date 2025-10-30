Option Compare Database

Private Sub btnDeleteRule_Click()
    Dim TypeSelect As String
    Dim ValueSelect As String
    Dim DLSelect As Integer
    Dim sqlDeleteRule As String
    Dim EMP_IDSelect As String
    If Me.listRule.ListIndex <> -1 Then
        TypeSelect = Me.listRule.Column(1, Me.listRule.ListIndex)
        ValueSelect = Me.listRule.Column(2, Me.listRule.ListIndex)
        DLSelect = Me.listRule.Column(3, Me.listRule.ListIndex)
        EMP_IDSelect = Me.listRule.Column(4, Me.listRule.ListIndex)
        
        Select Case TypeSelect
                Case "Location"
                    sqlDeleteRule = "DELETE FROM dbo_DL_RULE_LOC WHERE DLID=" & DLSelect & " AND E_Location='" & ValueSelect & "'"
                Case "TREE"
                    sqlDeleteRule = "DELETE FROM dbo_PS_DL_RULE_TREE WHERE DLID=" & DLSelect & " AND EMP_ID=" & EMP_IDSelect
                Case "User"
                    sqlDeleteRule = "DELETE FROM dbo_DL_RULE_USER WHERE DLID=" & DLSelect & " AND EMP_ID=" & EMP_IDSelect
        End Select
    Else
        MsgBox ("No rule selected.")
        Exit Sub
    End If
    
    DoCmd.SetWarnings False
    DoCmd.RunSQL (sqlDeleteRule)
    DoCmd.SetWarnings True
    
    
    Call RefreshList
End Sub

Private Sub cboList_AfterUpdate()
    Call RefreshList
End Sub

Private Sub cboRule_AfterUpdate()
    If (cboRule.Value = "User") Then
      Me.lblData.Caption = "Name"
      cboData.RowSource = "SELECT EmployeeName, EmployeeID FROM dbo_Employee_List"
      cboData.Value = ""
    End If
    If (cboRule.Value = "Location") Then
      Me.lblData.Caption = "Location"
      cboData.RowSource = "SELECT DISTINCT E_Location FROM dbo_Employee_List"
      cboData.Value = ""
    End If
End Sub


Private Sub Command5_Click()
    'Dim conn As Object
    'Set conn = CreateObject("ADODB.Connection")
    'Dim rsEmployee As Object
    'Set rsEmployee = CreateObject("ADODB.Recordset")
    'Dim rsRule_Loc As Object
    'Set rsRule_Loc = CreateObject("ADODB.Recordset")
    'Dim sqlInsert As String
    'conn.ConnectionString = "Provider=SQLOLEDB;Data Source=CORPOPERATIONS;Initial Catalog=DListDB;USER ID=DListAdmin;Password=;Trusted_Connection=No"
    
    'conn.Open
    'DoCmd.SetWarnings False
    'rsEmployee.Open "SELECT * FROM Employee_List", conn
    'conn.Close
    'DoCmd.RunSQL ("DELETE FROM Employee")
    'Do While Not rsEmployee.EOF
    '    sqlInsert = "INSERT INTO Employee (EmployeeID, EmployeeName, FirstName, LastName, JobTitle, HireDate, Location, SupervisoryOrg, Manager, M_EmployeeNumber, Status, InactiveDate, Username, Email) VALUES (" & rsEmployee("EmployeeID").Value & ",'" & rsEmployee("EmployeeName").Value & "','" & rsEmployee("FirstName").Value & "','" & rsEmployee("LastName").Value & "','" & rsEmployee("JobTitle").Value & "','" & rsEmployee("HireDate").Value & "','" & rsEmployee("E_Location").Value & "','" & rsEmployee("SupervisoryOrg").Value & "','" & rsEmployee("Manager").Value & "','" & rsEmployee("M_EmployeeID").Value & "','" & rsEmployee("E_Status").Value & "','" & rsEmployee("InactiveDate").Value & "','" & rsEmployee("Username").Value & "','" & rsEmployee("Email").Value & "')"
     '   'MsgBox (sqlInsert)
    '    DoCmd.RunSQL (sqlInsert)
    '    'MsgBox (rsEmployee("EmployeeID").Value)
    '    rsEmployee.MoveNext
    'Loop
    
    'DoCmd.SetWarnings True
End Sub

Private Sub btnAddRule_Click()
    Dim sqlAddRule As String
    If cboRule.Value = "" Then
        MsgBox ("No Rule Selected")
        Exit Sub
    End If
    
    If cboData.Value = "" Then
        MsgBox ("No Value Selected")
        Exit Sub
    End If
    
    Select Case cboRule.Value
        Case "Location"
            sqlAddRule = "INSERT INTO dbo_DL_RULE_LOC VALUES(" & cboList.Column(1) & ",'" & cboData.Value & "','" & cboInclude.Value & "')"
        Case "Tree"
            sqlAddRule = "INSERT INTO dbo_PS_DL_RULE_TREE VALUES(" & cboList.Column(1) & ",'" & cboData.Column(1) & "','" & cboInclude.Value & "')"
        Case "User"
            sqlAddRule = "INSERT INTO dbo_DL_RULE_USER VALUES(" & cboList.Column(1) & ",'" & cboData.Column(1) & "','" & cboInclude.Value & "')"
        Case Else
            MsgBox ("Invalid Rule")
            Exit Sub
    End Select
    DoCmd.SetWarnings False
    DoCmd.RunSQL (sqlAddRule)
    DoCmd.SetWarnings True
    Call RefreshList
    
End Sub

Private Sub Command17_Click()
    MsgBox (cboList.Column(1))
End Sub

Private Sub Form_Load()
    Call RefreshList
End Sub

Private Function RefreshList()
    listRule.RowSource = "SELECT TYPE_FLAG,'Location' as Rule, E_Location as Data, DLID, '' as EmployeeID FROM dbo_DL_RULE_LOC WHERE DLID = " & cboList.Column(1) & " UNION SELECT TYPE_FLAG, 'Tree' as Rule, dbo_Employee_List.EmployeeName as Data,  dbo_PS_DL_RULE_TREE.DLID, dbo_Employee_List.EmployeeID FROM dbo_PS_DL_RULE_TREE INNER JOIN dbo_Employee_List ON dbo_PS_DL_RULE_TREE.EMP_ID = dbo_Employee_List.EmployeeID WHERE dbo_PS_DL_RULE_TREE.DLID = " & cboList.Column(1) & " UNION SELECT TYPE_FLAG, 'User' as Rule, dbo_Employee_List.EmployeeName as Data,  dbo_DL_RULE_USER.DLID, dbo_Employee_List.EmployeeID FROM dbo_DL_RULE_USER INNER JOIN dbo_Employee_List ON dbo_DL_RULE_USER.EMP_ID = dbo_Employee_List.EmployeeID WHERE dbo_DL_RULE_USER.DLID=" & cboList.Column(1)
End Function
